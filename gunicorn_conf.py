# START OF FILE: gunicorn_conf.py

import asyncio
from telegram import Update, Bot
from telegram.ext import Application
from src.shared.logger import logger
from src.shared.config import PUBLIC_APP_URL
from src.infra.clients.supabase_repo import SupabaseRepo

def when_ready(server):
    """
    Этот хук выполняется ОДИН РАЗ, когда главный процесс Gunicorn готов.
    Идеальное место для установки вебхуков.
    """
    logger.info("Gunicorn master process is ready. Setting webhooks...")
    
    async def set_webhooks():
        supabase_repo = SupabaseRepo()
        clients = supabase_repo.get_active_clients()
        if not clients:
            logger.warning("No active clients found for webhook setup.")
            return

        for client in clients:
            token = client.get('bot_token')
            if not token:
                continue
            
            try:
                bot = Bot(token=token)
                webhook_url = f"{PUBLIC_APP_URL}/{token}"
                if not (await bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)):
                    logger.error(f"Failed to set webhook for bot ...{token[-4:]} to {webhook_url}")
                else:
                    logger.info(f"Webhook set for bot ...{token[-4:]} to {webhook_url}")
            except Exception as e:
                logger.error(f"Error setting webhook for bot ...{token[-4:]}: {e}", exc_info=True)

    # Запускаем асинхронную функцию в новом цикле событий
    try:
        asyncio.run(set_webhooks())
    except Exception as e:
        logger.error(f"An error occurred during webhook setup: {e}", exc_info=True)

# END OF FILE: gunicorn_conf.py