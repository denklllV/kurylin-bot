# START OF FILE: main.py

import sys, os, asyncio, uvicorn
from typing import Dict

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, ContextTypes, ExtBot

from src.shared.logger import logger
from src.shared.config import PUBLIC_APP_URL, PORT, RUN_MODE, GET_NAME, GET_DEBT, GET_INCOME, GET_REGION
from src.infra.clients.supabase_repo import SupabaseRepo
from src.infra.clients.openrouter_client import OpenRouterClient
from src.infra.clients.hf_whisper_client import WhisperClient
from src.app.services.ai_service import AIService
from src.app.services.lead_service import LeadService
from src.app.services.analytics_service import AnalyticsService
from src.api.telegram import handlers

# (Функции context_injector_middleware и register_handlers остаются без изменений)
client_config_cache: Dict[str, Dict] = {}
async def context_injector_middleware(...) -> bool: ...
def register_handlers(app: Application): ...

async def main() -> None:
    logger.info(f"Starting multi-tenant bot in {RUN_MODE} mode...")

    supabase_repo = SupabaseRepo()
    clients = supabase_repo.get_active_clients()
    if not clients:
        logger.error("No active clients found. Shutting down."); return

    for client in clients:
        client_config_cache[client['bot_token']] = client

    # --- Инициализация ЕДИНОГО Application ---
    app = Application.builder().token(clients[0]['bot_token']).build()
    
    app.add_handler(MessageHandler(filters.ALL, context_injector_middleware), group=-1)
    register_handlers(app)

    # ... (Инициализация и добавление сервисов в bot_data без изменений) ...
    
    if RUN_MODE == 'WEBHOOK':
        await app.bot.set_webhook(url=f"{PUBLIC_APP_URL}/{clients[0]['bot_token']}", allowed_updates=Update.ALL_TYPES)

        # --- ИСПРАВЛЕННАЯ И ФИНАЛЬНАЯ ЛОГИКА ЗАПУСКА ---
        async with app:
            await app.start()
            logger.info(f"Starting webserver on 0.0.0.0:{PORT}...")
            await app.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=clients[0]['bot_token'], # Важно для PTB, чтобы он знал, что слушать
                webhook_url=PUBLIC_APP_URL,
                allowed_updates=Update.ALL_TYPES
            )
            # await app.stop() # Не нужен, run_webhook блокирует

    else: # POLLING
        logger.info("Starting polling...")
        await app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"An unhandled exception occurred in main: {e}", exc_info=True)

# END OF FILE: main.py