# START OF FILE: main.py

import sys
import os

# Добавляем корень проекта в путь Python
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler

# Импортируем все необходимое из новой структуры
from src.shared.logger import logger
from src.shared.config import TELEGRAM_TOKEN, PORT, PUBLIC_APP_URL, RUN_MODE, GET_NAME, GET_DEBT, GET_INCOME, GET_REGION

# Импортируем клиентов и сервисы
from src.infra.clients.supabase_repo import SupabaseRepo
from src.infra.clients.openrouter_client import OpenRouterClient
from src.infra.clients.hf_whisper_client import WhisperClient
from src.app.services.ai_service import AIService
from src.app.services.lead_service import LeadService

# Импортируем хендлеры
from src.api.telegram import handlers

def main() -> None:
    """Сборка и запуск бота на новой архитектуре."""
    logger.info(f"Starting bot in {RUN_MODE} mode...")

    # 1. Инициализация зависимостей (Dependency Injection)
    supabase_repo = SupabaseRepo()
    or_client = OpenRouterClient()
    whisper_client = WhisperClient()
    
    # 2. Сборка приложения Telegram
    # ИСПРАВЛЕНИЕ ЗДЕСЬ: Сначала строим приложение, потом добавляем bot_data
    builder = Application.builder().token(TELEGRAM_TOKEN)
    application = builder.build()
    
    # 3. Передаем инстансы сервисов в bot_data
    # Это единственный правильный способ передать зависимости в хендлеры
    ai_service = AIService(or_client, whisper_client)
    lead_service = LeadService(supabase_repo, application.bot) # Теперь мы используем application.bot
    
    application.bot_data['ai_service'] = ai_service
    application.bot_data['lead_service'] = lead_service
    
    # 4. Регистрация обработчиков
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
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(contact_button_filter, handlers.contact_human))
    application.add_handler(MessageHandler(filters.VOICE, handlers.handle_voice_message))
    
    # Важно, чтобы этот обработчик был одним из последних, т.к. он ловит "любой" текст
    text_filter = filters.TEXT & ~filters.COMMAND & ~form_button_filter & ~contact_button_filter
    application.add_handler(MessageHandler(text_filter, handlers.handle_text_message))

    logger.info("All handlers have been registered.")
    
    # 5. Запуск бота в нужном режиме
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
