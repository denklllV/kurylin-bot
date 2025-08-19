# START OF FILE: main.py

import sys
import os
import asyncio
from typing import Dict

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, CallbackQueryHandler, ContextTypes, ExtBot, Updater
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

# Глобальный словарь для хранения инстансов Application для каждого бота
running_bots: Dict[str, Application] = {}

async def router_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Маршрутизирует входящие обновления к правильному инстансу Application."""
    token = context.bot.token
    if token in running_bots:
        await running_bots[token].process_update(update)

def register_handlers(app: Application):
    """Регистрирует все обработчики для одного инстанса Application."""
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
    or_client = OpenRouterClient()
    whisper_client = WhisperClient()
    
    clients = supabase_repo.get_active_clients()
    if not clients:
        logger.error("No active clients found. Shutting down.")
        return

    generic_bot = ExtBot(token=clients[0]['bot_token'])
    ai_service = AIService(or_client, whisper_client, supabase_repo)
    lead_service = LeadService(supabase_repo, generic_bot)
    analytics_service = AnalyticsService(supabase_repo)

    for client in clients:
        token = client['bot_token']
        app = Application.builder().token(token).build()

        app.bot_data['ai_service'] = ai_service
        app.bot_data['lead_service'] = lead_service
        app.bot_data['analytics_service'] = analytics_service
        app.bot_data['last_debug_info'] = {}
        app.bot_data['client_id'] = client['id']
        app.bot_data['manager_contact'] = client['manager_contact']

        register_handlers(app)
        running_bots[token] = app
        logger.info(f"Client '{client['client_name']}' (ID: {client['id']}) configured.")

    if RUN_MODE == 'WEBHOOK':
        # --- ИСПРАВЛЕННАЯ ЛОГИКА ЗАПУСКА WEBHOOK ---
        # 1. Инициализируем все боты и устанавливаем для них вебхуки
        for token, app_instance in running_bots.items():
            await app_instance.initialize()
            webhook_url = f"{PUBLIC_APP_URL}/{token}"
            await app_instance.bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)
            logger.info(f"Webhook set for bot with token ending in ...{token[-4:]} to URL: {webhook_url}")

        # 2. Создаем "диспетчера", который будет слушать веб-сервер
        # Он использует токен только для инициализации, но принимает обновления для всех
        dispatcher_app = Application.builder().token(clients[0]['bot_token']).updater(None).build()
        dispatcher_app.add_handler(MessageHandler(filters.ALL, router_callback))
        await dispatcher_app.initialize()

        # 3. Запускаем веб-сервер через `run_webhook` на диспетчере
        logger.info(f"Starting shared webhook server on port {PORT}...")
        await dispatcher_app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=clients[0]['bot_token'], # url_path обязателен, но Telegram будет его игнорировать
            webhook_url=PUBLIC_APP_URL
        )
        
    elif RUN_MODE == 'POLLING':
        logger.info("Starting all clients in POLLING mode...")
        # Инициализируем и запускаем каждый бот в режиме поллинга
        async with Application.builder().token(clients[0]['bot_token']).build() as template_app:
            await asyncio.gather(
                *(app.run_polling(allowed_updates=Update.ALL_TYPES) for app in running_bots.values())
            )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot shutdown requested.")
    except Exception as e:
        logger.error(f"An unhandled exception occurred: {e}", exc_info=True)

# END OF FILE: main.py