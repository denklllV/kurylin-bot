# START OF FILE: main.py

import sys
import os

# Добавляем корень проекта в путь Python
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler

# Импортируем все необходимое из новой структуры
from src.shared.logger import logger
from src.shared.config import TELEGRAM_TOKEN, PORT, WEBHOOK_URL, RUN_MODE, GET_NAME, GET_DEBT, GET_INCOME, GET_REGION

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
    # Сначала создаем "адаптеры" слоя инфраструктуры
    supabase_repo = SupabaseRepo()
    or_client = OpenRouterClient()
    whisper_client = WhisperClient()
    
    # Затем создаем сервисы, передавая им зависимости
    # Временное решение для `bot` в LeadService
    temp_bot_instance = Application.builder().token(TELEGRAM_TOKEN).build().bot
    
    ai_service = AIService(or_client, whisper_client)
    lead_service = LeadService(supabase_repo, temp_bot_instance)

    # 2. Сборка приложения Telegram
    # Мы передаем инстансы сервисов в `bot_data`, чтобы они были доступны в хендлерах
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .bot_data({'ai_service': ai_service, 'lead_service': lead_service})
        .build()
    )
    
    # 3. Регистрация обработчиков
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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_text_message))

    logger.info("All handlers have been registered.")
    
    # 4. Запуск бота в нужном режиме
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