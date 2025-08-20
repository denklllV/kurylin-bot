# START OF FILE: main.py

import sys
import os
import asyncio
import uvicorn
from typing import Dict

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from fastapi import FastAPI, Request, Response
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

# --- 1. Инициализация FastAPI и глобальных хранилищ ---
fastapi_app = FastAPI(docs_url=None, redoc_url=None) # Отключаем авто-документацию
bots: Dict[str, Application] = {}
client_configs: Dict[str, Dict] = {}

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

async def setup_bot(token: str, client_config: Dict, common_services: Dict) -> Application:
    """Создает, настраивает и инициализирует один инстанс бота."""
    app = Application.builder().token(token).build()
    
    # Заполняем bot_data общими сервисами и уникальными данными клиента
    app.bot_data.update(common_services)
    app.bot_data['client_id'] = client_config['id']
    app.bot_data['manager_contact'] = client_config['manager_contact']
    # ИЗМЕНЕНИЕ: Сохраняем конфигурацию квиза (может быть None) в контекст бота
    app.bot_data['quiz_data'] = client_config.get('quiz_data')
    
    register_handlers(app)
    
    await app.initialize()
    await app.start()
    
    if RUN_MODE == 'WEBHOOK':
        webhook_url = f"{PUBLIC_APP_URL}/{token}"
        if not (await app.bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)):
            logger.error(f"Failed to set webhook for bot ...{token[-4:]} to {webhook_url}")
        else:
            logger.info(f"Webhook set for bot ...{token[-4:]} to {webhook_url}")

    return app

# --- 2. Роут для приема вебхуков от Telegram ---
@fastapi_app.post("/{bot_token}")
async def handle_webhook(bot_token: str, request: Request):
    """Единая точка входа для всех вебхуков."""
    if bot_token in bots:
        update_json = await request.json()
        update = Update.de_json(update_json, bots[bot_token].bot)
        await bots[bot_token].process_update(update)
        return Response(status_code=200)
    else:
        logger.warning(f"Received update for unknown token ending in ...{bot_token[-4:]}")
        return Response(status_code=404)

# --- 3. Логика запуска и остановки ---
@fastapi_app.on_event("startup")
async def startup_event():
    """Выполняется при старте FastAPI-приложения."""
    logger.info("Application startup...")
    
    supabase_repo = SupabaseRepo()
    or_client = OpenRouterClient()
    whisper_client = WhisperClient()
    
    # Создаем "пустышку" бота для сервисов, которым он нужен
    generic_bot = ExtBot(token="12345:ABCDE") 
    
    common_services = {
        'ai_service': AIService(or_client, whisper_client, supabase_repo),
        'lead_service': LeadService(supabase_repo, generic_bot),
        'analytics_service': AnalyticsService(supabase_repo),
        'last_debug_info': {}
    }

    clients = supabase_repo.get_active_clients()
    if not clients:
        logger.error("No active clients found. Application will not start any bots.")
        return

    for client in clients:
        token = client['bot_token']
        client_configs[token] = client
        bot_app = await setup_bot(token, client, common_services)
        bots[token] = bot_app
    
    logger.info(f"Initialized {len(bots)} bot(s).")
    
@fastapi_app.on_event("shutdown")
async def shutdown_event():
    """Выполняется при остановке FastAPI-приложения."""
    logger.info("Application shutdown...")
    for app in bots.values():
        await app.stop()
        await app.shutdown()

# --- 4. Основная точка входа для запуска сервера ---
def main():
    if RUN_MODE == 'POLLING':
        logger.error("POLLING mode is not supported in this architecture. Please use WEBHOOK.")
        return

    logger.info("Starting Uvicorn server...")
    uvicorn.run(
        app=fastapi_app,
        host="0.0.0.0",
        port=PORT
    )

if __name__ == "__main__":
    main()

# END OF FILE: main.py