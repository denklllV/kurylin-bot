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
fastapi_app = FastAPI(docs_url=None, redoc_url=None)
bots: Dict[str, Application] = {}
client_configs: Dict[str, Dict] = {}

def register_handlers(app: Application):
    """Регистрирует все обработчики для одного инстанса Application."""
    # --- Фильтры для кнопок ---
    form_button_filter = filters.Regex('^📝 Заполнить анкету$')
    contact_button_filter = filters.Regex('^🧑‍💼 Связаться с человеком$')
    cancel_filter = filters.Regex('^Отмена$')
    quiz_button_filter = filters.Regex('^🎯 Квиз$')
    
    # --- Фильтры для кнопок админ-панели ---
    stats_button_filter = filters.Regex('^📊 Статистика$')
    export_button_filter = filters.Regex('^📤 Экспорт лидов$')
    prompt_menu_button_filter = filters.Regex('^📜 Управление промптом$')
    broadcast_menu_button_filter = filters.Regex('^📣 Рассылка$')
    debug_button_filter = filters.Regex('^🕵️‍♂️ Отладка ответа$')

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
    
    # --- Команды ---
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("admin", handlers.admin_panel))
    app.add_handler(CommandHandler("stats", handlers.stats))
    app.add_handler(CommandHandler("export_leads", handlers.export_leads))
    app.add_handler(CommandHandler("last_answer", handlers.last_answer_debug))
    app.add_handler(CommandHandler("health_check", handlers.health_check))
    app.add_handler(CommandHandler("get_prompt", handlers.get_prompt))
    app.add_handler(CommandHandler("set_prompt", handlers.set_prompt))
    app.add_handler(CommandHandler("broadcast", handlers.broadcast_real))
    app.add_handler(CommandHandler("broadcast_dry_run", handlers.broadcast_dry_run))

    # --- Кнопки админ-панели ---
    app.add_handler(MessageHandler(stats_button_filter, handlers.stats))
    app.add_handler(MessageHandler(export_button_filter, handlers.export_leads))
    app.add_handler(MessageHandler(prompt_menu_button_filter, handlers.prompt_management_menu))
    app.add_handler(MessageHandler(broadcast_menu_button_filter, handlers.broadcast_menu))
    app.add_handler(MessageHandler(debug_button_filter, handlers.last_answer_debug))

    # --- Инлайн-кнопки ---
    app.add_handler(CallbackQueryHandler(handlers.quiz_answer, pattern='^quiz_step_'))
    app.add_handler(CallbackQueryHandler(handlers.start_quiz_from_prompt, pattern='^start_quiz_from_prompt$'))

    # --- Обычные кнопки и сообщения ---
    app.add_handler(MessageHandler(quiz_button_filter, handlers.start_quiz))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(contact_button_filter, handlers.contact_human))
    app.add_handler(MessageHandler(filters.VOICE, handlers.handle_voice_message))
    
    # --- Фильтр для обычных текстовых сообщений (должен быть в конце) ---
    text_filter = (
        filters.TEXT & ~filters.COMMAND & ~form_button_filter & 
        ~contact_button_filter & ~quiz_button_filter & ~stats_button_filter &
        ~export_button_filter & ~prompt_menu_button_filter & 
        ~broadcast_menu_button_filter & ~debug_button_filter
    )
    app.add_handler(MessageHandler(text_filter, handlers.handle_text_message))

async def setup_bot(token: str, client_config: Dict, common_services: Dict) -> Application:
    app = Application.builder().token(token).build()
    
    app.bot_data.update(common_services)
    app.bot_data['client_id'] = client_config['id']
    app.bot_data['manager_contact'] = client_config['manager_contact']
    app.bot_data['quiz_data'] = client_config.get('quiz_data')
    app.bot_data['google_sheet_id'] = client_config.get('google_sheet_id')
    
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

@fastapi_app.post("/{bot_token}")
async def handle_webhook(bot_token: str, request: Request):
    if bot_token in bots:
        update_json = await request.json()
        update = Update.de_json(update_json, bots[bot_token].bot)
        await bots[bot_token].process_update(update)
        return Response(status_code=200)
    else:
        logger.warning(f"Received update for unknown token ending in ...{bot_token[-4:]}")
        return Response(status_code=404)

@fastapi_app.on_event("startup")
async def startup_event():
    logger.info("Application startup...")
    supabase_repo = SupabaseRepo()
    or_client = OpenRouterClient()
    whisper_client = WhisperClient()
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
    logger.info("Application shutdown...")
    for app in bots.values():
        await app.stop()
        await app.shutdown()

def main():
    if RUN_MODE == 'POLLING':
        logger.error("POLLING mode is not supported in this architecture. Please use WEBHOOK.")
        return
    logger.info("Starting Uvicorn server...")
    uvicorn.run(app=fastapi_app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()

# END OF FILE: main.py