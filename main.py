# START OF FILE: main.py

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler

from src.shared.logger import logger
from src.shared.config import TELEGRAM_TOKEN, PORT, PUBLIC_APP_URL, RUN_MODE, GET_NAME, GET_DEBT, GET_INCOME, GET_REGION

from src.infra.clients.supabase_repo import SupabaseRepo
from src.infra.clients.openrouter_client import OpenRouterClient
from src.infra.clients.hf_whisper_client import WhisperClient
# ИЗМЕНЕНИЕ: Возвращаем наш легковесный HF API клиент
from src.infra.clients.hf_embed_client import EmbeddingClient
from src.app.services.ai_service import AIService
from src.app.services.lead_service import LeadService

from src.api.telegram import handlers

def main() -> None:
    logger.info(f"Starting bot in {RUN_MODE} mode...")

    # 1. Инициализация зависимостей
    supabase_repo = SupabaseRepo()
    or_client = OpenRouterClient()
    whisper_client = WhisperClient()
    # ИЗМЕНЕНИЕ: Создаем инстанс HF API клиента
    embed_client = EmbeddingClient()

    # 2. Сборка приложения Telegram
    builder = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
    )
    application = builder.build()
    
    # 3. Передаем инстансы сервисов в bot_data
    ai_service = AIService(or_client, whisper_client, embed_client, supabase_repo)
    lead_service = LeadService(supabase_repo, application.bot)
    
    application.bot_data['ai_service'] = ai_service
    application.bot_data['lead_service'] = lead_service
    application.bot_data['last_debug_info'] = {}
    
    # 4. Регистрация обработчиков
    # ... (код без изменений) ...
    form_button_filter = filters.Regex('^📝 Заполнить анкету$')
    contact_button_filter = filters.Regex('^🧑‍💼 Связаться с человеком$')
    cancel_filter = filters.Regex('^Отмена$')

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
    
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("last_answer", handlers.last_answer_debug))
    application.add_handler(CommandHandler("health_check", handlers.health_check))
    
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(contact_button_filter, handlers.contact_human))
    application.add_handler(MessageHandler(filters.VOICE, handlers.handle_voice_message))
    
    text_filter = filters.TEXT & ~filters.COMMAND & ~form_button_filter & ~contact_button_filter
    application.add_handler(MessageHandler(text_filter, handlers.handle_text_message))

    logger.info("All handlers have been registered.")
    
    # 5. Запуск бота
    # ... (код без изменений) ...
    if RUN_MODE == 'POLLING':
        logger.info("Running in POLLING mode for local testing.")
        application.run_polling()
    else:
        webhook_url = f"{PUBLIC_APP_URL}/{TELEGRAM_TOKEN}"
        logger.info(f"Running in WEBHOOK mode. URL: {webhook_url}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TELEGRAM_TOKEN,
            webhook_url=webhook_url
        )

if __name__ == "__main__":
    main()

# END OF FILE: main.py