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
    PUBLIC_APP_URL, PORT, RUN_MODE, 
    GET_NAME, GET_DEBT, GET_INCOME, GET_REGION,
    GET_BROADCAST_MESSAGE, GET_BROADCAST_MEDIA, CONFIRM_BROADCAST
)
from src.infra.clients.supabase_repo import SupabaseRepo
from src.infra.clients.openrouter_client import OpenRouterClient
from src.infra.clients.hf_whisper_client import WhisperClient
from src.app.services.ai_service import AIService
from src.app.services.lead_service import LeadService
from src.app.services.analytics_service import AnalyticsService
# ИЗМЕНЕНИЕ: Импортируем из новых, разделенных файлов
from src.api.telegram import user_handlers, admin_handlers

fastapi_app = FastAPI(docs_url=None, redoc_url=None)
bots: Dict[str, Application] = {}
client_configs: Dict[str, Dict] = {}

def register_handlers(app: Application):
    # --- Фильтры для кнопок ---
    form_button_filter = filters.Regex('^📝 Заполнить анкету$')
    contact_button_filter = filters.Regex('^🧑‍💼 Связаться с человеком$')
    cancel_filter = filters.Regex('^Отмена$|^❌ Отмена$')
    quiz_button_filter = filters.Regex('^🎯 Квиз$')
    
    stats_button_filter = filters.Regex('^📊 Статистика$')
    export_button_filter = filters.Regex('^📤 Экспорт лидов$')
    prompt_menu_button_filter = filters.Regex('^📜 Управление промптом$')
    broadcast_menu_button_filter = filters.Regex('^📣 Рассылка$')
    debug_button_filter = filters.Regex('^🕵️‍♂️ Отладка ответа$')
    quiz_management_button_filter = filters.Regex('^🧩 Управление квизом$')

    # --- Обработчик анкеты (из user_handlers) ---
    form_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(form_button_filter, user_handlers.start_form)],
        states={
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_handlers.get_name)],
            GET_DEBT: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_handlers.get_debt)],
            GET_INCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_handlers.get_income)],
            GET_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_handlers.get_region)],
        },
        fallbacks=[CommandHandler('cancel', user_handlers.cancel), MessageHandler(cancel_filter, user_handlers.cancel)],
    )

    # --- Обработчик Мастера Рассылок (из admin_handlers) ---
    broadcast_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(broadcast_menu_button_filter, admin_handlers.broadcast_start)],
        states={
            GET_BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.broadcast_get_message)],
            GET_BROADCAST_MEDIA: [
                CommandHandler('skip', admin_handlers.broadcast_skip_media),
                MessageHandler(filters.PHOTO | filters.Document.ALL, admin_handlers.broadcast_get_media)
            ],
            CONFIRM_BROADCAST: [
                MessageHandler(filters.Regex('^✅ Отправить всем$'), admin_handlers.broadcast_send),
                MessageHandler(filters.Regex('^📝 Редактировать$'), admin_handlers.broadcast_start)
            ]
        },
        fallbacks=[CommandHandler('cancel', admin_handlers.broadcast_cancel), MessageHandler(cancel_filter, admin_handlers.broadcast_cancel)],
    )
    
    # --- Регистрация команд ---
    app.add_handler(CommandHandler("start", user_handlers.start))
    app.add_handler(CommandHandler("admin", admin_handlers.admin_panel))
    app.add_handler(CommandHandler("stats", admin_handlers.stats))
    app.add_handler(CommandHandler("export_leads", admin_handlers.export_leads))
    app.add_handler(CommandHandler("last_answer", admin_handlers.last_answer_debug))
    app.add_handler(CommandHandler("health_check", admin_handlers.health_check))
    app.add_handler(CommandHandler("get_prompt", admin_handlers.get_prompt))
    app.add_handler(CommandHandler("set_prompt", admin_handlers.set_prompt))

    # --- Кнопки админ-панели ---
    app.add_handler(MessageHandler(stats_button_filter, admin_handlers.stats))
    app.add_handler(MessageHandler(export_button_filter, admin_handlers.export_leads))
    app.add_handler(MessageHandler(prompt_menu_button_filter, admin_handlers.prompt_management_menu))
    app.add_handler(MessageHandler(debug_button_filter, admin_handlers.last_answer_debug))
    app.add_handler(MessageHandler(quiz_management_button_filter, admin_handlers.quiz_management_menu))

    # --- Инлайн-кнопки (user_handlers) ---
    app.add_handler(CallbackQueryHandler(user_handlers.quiz_answer, pattern='^quiz_step_'))
    app.add_handler(CallbackQueryHandler(user_handlers.start_quiz_from_prompt, pattern='^start_quiz_from_prompt$'))

    # --- Диалоговые обработчики ---
    app.add_handler(form_conv_handler)
    app.add_handler(broadcast_conv_handler)

    # --- Обычные кнопки и сообщения (user_handlers) ---
    app.add_handler(MessageHandler(quiz_button_filter, user_handlers.start_quiz))
    app.add_handler(MessageHandler(contact_button_filter, user_handlers.contact_human))
    app.add_handler(MessageHandler(filters.VOICE, user_handlers.handle_voice_message))
    
    # --- Фильтр для обычных текстовых сообщений (должен быть в конце) ---
    text_filter = (
        filters.TEXT & ~filters.COMMAND & ~form_button_filter & 
        ~contact_button_filter & ~quiz_button_filter & ~stats_button_filter &
        ~export_button_filter & ~prompt_menu_button_filter & 
        ~broadcast_menu_button_filter & ~debug_button_filter &
        ~quiz_management_button_filter &
        ~filters.Regex('^✅ Отправить всем$') & ~filters.Regex('^📝 Редактировать$') & ~cancel_filter
    )
    app.add_handler(MessageHandler(text_filter, user_handlers.handle_text_message))

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
        update = Update.de_json(await request.json(), bots[bot_token].bot)
        await bots[bot_token].process_update(update)
        return Response(status_code=200)
    return Response(status_code=404)

@fastapi_app.on_event("startup")
async def startup_event():
    logger.info("Application startup...")
    supabase_repo = SupabaseRepo()
    common_services = {
        'ai_service': AIService(OpenRouterClient(), WhisperClient(), supabase_repo),
        'lead_service': LeadService(supabase_repo, ExtBot(token="12345:ABCDE")),
        'analytics_service': AnalyticsService(supabase_repo),
        'last_debug_info': {}
    }
    clients = supabase_repo.get_active_clients()
    if not clients:
        logger.error("No active clients found.")
        return
    for client in clients:
        bots[client['bot_token']] = await setup_bot(client['bot_token'], client, common_services)
    logger.info(f"Initialized {len(bots)} bot(s).")
    
@fastapi_app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown...")
    for app in bots.values():
        await app.stop()
        await app.shutdown()

def main():
    if RUN_MODE == 'POLLING':
        logger.error("POLLING mode is not supported.")
        return
    logger.info("Starting Uvicorn server...")
    uvicorn.run(app=fastapi_app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()

# END OF FILE: main.py