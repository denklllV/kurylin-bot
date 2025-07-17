# main.py
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler

from src.config import TELEGRAM_TOKEN, PORT, WEBHOOK_URL, logger
from src.config import GET_NAME, GET_DEBT, GET_INCOME, GET_REGION
from src.handlers import (
    start,
    handle_text_message,
    handle_voice_message,
    whoami,
    start_form,
    get_name,
    get_debt,
    get_income,
    get_region,
    cancel,
    contact_human,
    handle_broadcast,
    handle_broadcast_dry_run,
)

def main() -> None:
    """Сборка и запуск бота."""
    logger.info("Сборка и настройка приложения...")
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    form_button_filter = filters.Regex('^📝 Заполнить анкету$')
    contact_button_filter = filters.Regex('^🧑‍💼 Связаться с человеком$')
    cancel_filter = filters.Regex('^Отмена$')

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(form_button_filter, start_form)],
        states={
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~cancel_filter, get_name)],
            GET_DEBT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~cancel_filter, get_debt)],
            GET_INCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~cancel_filter, get_income)],
            GET_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~cancel_filter, get_region)],
        },
        fallbacks=[CommandHandler('cancel', cancel), MessageHandler(cancel_filter, cancel)],
    )

    # Регистрируем административные команды
    application.add_handler(CommandHandler("broadcast", handle_broadcast))
    application.add_handler(CommandHandler("broadcast_dry_run", handle_broadcast_dry_run))

    # Регистрируем команды и кнопки для обычных пользователей
    application.add_handler(CommandHandler("whoami", whoami))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(contact_button_filter, contact_human))
    
    # Регистрируем обработчик голосовых
    application.add_handler(MessageHandler(filters.VOICE, handle_voice_message))
    
    # Регистрируем обработчик для ВСЕХ ОСТАЛЬНЫХ текстовых сообщений
    # Он должен игнорировать команды (~) и кнопки, которые обрабатываются выше
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~form_button_filter & ~contact_button_filter, # <-- ИЗМЕНЕНИЕ ЗДЕСЬ
        handle_text_message
    ))

    logger.info(f"Запуск бота на порту {PORT}...")
    
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()