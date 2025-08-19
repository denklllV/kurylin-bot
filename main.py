# START OF FILE: main.py

import sys
import os
import asyncio
from typing import Dict

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, CallbackQueryHandler, ContextTypes, ExtBot
)

from src.shared.logger import logger
from src.shared.config import (
    PUBLIC_APP_URL, PORT, RUN_MODE, GET_NAME, GET_DEBT, GET_INCOME, GET_REGION
)
from src.infra.clients.supabase_repo import SupabaseRepo
from src.infra.clients.openrouter_client import OpenRouterClient
from src.infra.clients.hf_whisper_client import WhisperClient
from src.app.services.ai_service import AIService
from src.app.services.lead_service import LeadService
from src.app.services.analytics_service import AnalyticsService
from src.api.telegram import handlers

# Глобальный кэш для хранения конфигураций клиентов: {token: client_data}
client_config_cache: Dict[str, Dict] = {}

async def context_injector_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Middleware: Определяет клиента по токену и "впрыскивает" его данные в context.
    Это ключевая часть новой архитектуры.
    """
    token = context.bot.token
    if token in client_config_cache:
        client_data = client_config_cache[token]
        # Важно: `bot_data` теперь будет уникальным для каждого запроса
        context.bot_data['client_id'] = client_data['id']
        context.bot_data['manager_contact'] = client_data['manager_contact']
        return True # Разрешаем дальнейшую обработку
    
    logger.warning(f"Received update for an unknown bot token ending in ...{token[-4:]}")
    return False # Блокируем обработку для неизвестных токенов

def register_handlers(app: Application):
    """Регистрирует все обработчики для нашего единственного приложения."""
    # Фильтры
    form_button_filter = filters.Regex('^📝 Заполнить анкету$')
    contact_button_filter = filters.Regex('^🧑‍💼 Связаться с человеком$')
    cancel_filter = filters.Regex('^Отмена$')
    quiz_button_filter = filters.Regex('^🎯 Квиз$')

    # Обработчик анкеты
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(form_button_filter, handlers.start_form)],
        states={
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~cancel_filter, handlers.get_name)],
            GET_DEBT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~cancel_filter, handlers.get_debt)],
            GET_INCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~cancel_filter, handlers.get_income)],
            GET_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~cancel_filter, handlers.get_region)],
        },
        fallbacks=[CommandHandler('cancel', handlers.cancel), MessageHandler(cancel_filter, handlers.cancel)],
    )
    
    # Команды
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("stats", handlers.stats))
    app.add_handler(CommandHandler("last_answer", handlers.last_answer_debug))
    app.add_handler(CommandHandler("health_check", handlers.health_check))
    
    # Обработчики инлайн-кнопок
    app.add_handler(CallbackQueryHandler(handlers.quiz_answer, pattern='^quiz_step_'))
    app.add_handler(CallbackQueryHandler(handlers.start_quiz_from_prompt, pattern='^start_quiz_from_prompt$'))

    # Обработчики кнопок главного меню
    app.add_handler(MessageHandler(quiz_button_filter, handlers.start_quiz))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(contact_button_filter, handlers.contact_human))
    
    # Обработчики сообщений
    app.add_handler(MessageHandler(filters.VOICE, handlers.handle_voice_message))
    text_filter = filters.TEXT & ~filters.COMMAND & ~form_button_filter & ~contact_button_filter & ~quiz_button_filter
    app.add_handler(MessageHandler(text_filter, handlers.handle_text_message))

async def main() -> None:
    logger.info(f"Starting multi-tenant bot in {RUN_MODE} mode...")

    supabase_repo = SupabaseRepo()
    clients = supabase_repo.get_active_clients()
    if not clients:
        logger.error("No active clients found. Shutting down.")
        return

    for client in clients:
        client_config_cache[client['bot_token']] = client

    # --- Инициализация ЕДИНОГО Application ---
    # Токен первого клиента используется только для инициализации
    app = Application.builder().token(clients[0]['bot_token']).build()

    # Вставляем наш middleware в группу -1, чтобы он выполнялся первым
    app.add_handler(MessageHandler(filters.ALL, context_injector_middleware), group=-1)

    register_handlers(app)

    # Инициализация общих сервисов
    or_client = OpenRouterClient()
    whisper_client = WhisperClient()
    generic_bot = ExtBot(token=clients[0]['bot_token'])
    
    ai_service = AIService(or_client, whisper_client, supabase_repo)
    lead_service = LeadService(supabase_repo, generic_bot)
    analytics_service = AnalyticsService(supabase_repo)

    # Заполняем `application.bot_data` общими сервисами, которые будут доступны всем
    app.bot_data['ai_service'] = ai_service
    app.bot_data['lead_service'] = lead_service
    app.bot_data['analytics_service'] = analytics_service
    app.bot_data['last_debug_info'] = {}

    if RUN_MODE == 'WEBHOOK':
        await app.initialize()
        for token in client_config_cache.keys():
             webhook_url = f"{PUBLIC_APP_URL}/{token}"
             temp_bot = ExtBot(token=token)
             await temp_bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)
             logger.info(f"Webhook set for bot ...{token[-4:]} to {webhook_url}")
        
        await app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=clients[0]['bot_token'], # Этот url_path используется для установки вебхука
            webhook_url=PUBLIC_APP_URL
        )
    else: # POLLING
        logger.info("Starting polling for all clients...")
        await app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot shutdown requested.")
    except Exception as e:
        logger.error(f"An unhandled exception occurred in main: {e}", exc_info=True)

# END OF FILE: main.py