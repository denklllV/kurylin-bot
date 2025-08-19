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

# Глобальные переменные
client_config_cache: Dict[str, Dict] = {}
running_bots: Dict[str, Application] = {}

async def context_injector_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Middleware для 'впрыскивания' контекста клиента."""
    token = context.bot.token
    if token in client_config_cache:
        client_data = client_config_cache[token]
        context.bot_data['client_id'] = client_data['id']
        context.bot_data['manager_contact'] = client_data['manager_contact']
        return True
    logger.warning(f"Update received for unknown bot token ending in ...{token[-4:]}")
    return False

def register_handlers(app: Application):
    """Регистрирует все обработчики для приложения."""
    # (Здесь ваш полный код register_handlers без изменений)
    form_button_filter = filters.Regex('^📝 Заполнить анкету$')
    contact_button_filter = filters.Regex('^🧑‍💼 Связаться с человеком$')
    cancel_filter = filters.Regex('^Отмена$')
    quiz_button_filter = filters.Regex('^🎯 Квиз$')
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
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("stats", handlers.stats))
    app.add_handler(CommandHandler("last_answer", handlers.last_answer_debug))
    app.add_handler(CommandHandler("health_check", handlers.health_check))
    app.add_handler(CallbackQueryHandler(handlers.quiz_answer, pattern='^quiz_step_'))
    app.add_handler(CallbackQueryHandler(handlers.start_quiz_from_prompt, pattern='^start_quiz_from_prompt$'))
    app.add_handler(MessageHandler(quiz_button_filter, handlers.start_quiz))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(contact_button_filter, handlers.contact_human))
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

    # --- Инициализация и настройка ЕДИНОГО ДИСПЕТЧЕРА ---
    # Токен здесь нужен только для инициализации, он будет заменяться в middleware
    app = Application.builder().token(clients[0]['bot_token']).build()
    
    app.add_handler(MessageHandler(filters.ALL, context_injector_middleware), group=-1)
    register_handlers(app)

    or_client = OpenRouterClient()
    whisper_client = WhisperClient()
    generic_bot = ExtBot(token=clients[0]['bot_token'])
    ai_service = AIService(or_client, whisper_client, supabase_repo)
    lead_service = LeadService(supabase_repo, generic_bot)
    analytics_service = AnalyticsService(supabase_repo)

    app.bot_data.update({
        'ai_service': ai_service,
        'lead_service': lead_service,
        'analytics_service': analytics_service,
        'last_debug_info': {}
    })
    
    # --- ИСПРАВЛЕННАЯ ЛОГИКА ЗАПУСКА ---
    try:
        await app.initialize() # 1. Инициализируем приложение

        if RUN_MODE == 'WEBHOOK':
            for token in client_config_cache.keys():
                webhook_url = f"{PUBLIC_APP_URL}/{token}"
                temp_bot = ExtBot(token=token)
                await temp_bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)
                logger.info(f"Webhook set for bot ...{token[-4:]} to {webhook_url}")
            
            # 2. Запускаем внутренние процессы, но НЕ блокируем выполнение
            await app.start()
            logger.info(f"Starting webserver on 0.0.0.0:{PORT}...")
            # 3. Стартуем веб-сервер uvicorn, который будет слушать запросы
            # и передавать их в `app.update_queue`
            import uvicorn
            webserver = uvicorn.Server(
                config=uvicorn.Config(
                    app=app.asgi_app,
                    host="0.0.0.0",
                    port=PORT,
                )
            )
            await webserver.serve()

        else: # POLLING
            logger.info("Starting polling...")
            await app.run_polling(allowed_updates=Update.ALL_TYPES)

    finally:
        logger.info("Shutting down bot...")
        await app.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot shutdown requested.")
    except Exception as e:
        logger.error(f"An unhandled exception occurred in main: {e}", exc_info=True)