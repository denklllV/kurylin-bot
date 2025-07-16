# main.py
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)

# --- Импорты из нашего проекта ---

# Сначала импортируем всю необходимую конфигурацию
from src.config import TELEGRAM_TOKEN, PORT, WEBHOOK_URL, logger

# Затем импортируем константы состояний для анкеты
from src.config import GET_NAME, GET_DEBT, GET_INCOME, GET_REGION

# Наконец, импортируем все наши функции-обработчики из модуля handlers
from src.handlers import (
    start,
    handle_message,
    start_form,
    get_name,
    get_debt,
    get_income,
    get_region,
    cancel,
    contact_human,
)

def main() -> None:
    """Главная функция, которая собирает и запускает бота."""
    logger.info("Сборка и настройка приложения...")
    
    # Создаем объект приложения, используя токен из конфига
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Определяем фильтры для кнопок, чтобы код был читаемее
    form_button_filter = filters.Regex('^📝 Заполнить анкету$')
    contact_button_filter = filters.Regex('^🧑‍💼 Связаться с человеком$')
    cancel_filter = filters.Regex('^Отмена$')

    # Собираем ConversationHandler, используя импортированные функции
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

    # Регистрируем все обработчики в приложении
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(contact_button_filter, contact_human))
    
    # Важно: обработчик текстовых сообщений должен быть одним из последних,
    # чтобы он не перехватывал команды и нажатия на кнопки
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~form_button_filter & ~contact_button_filter,
        handle_message
    ))

    logger.info(f"Запуск бота на порту {PORT}...")
    
    # Запускаем бота в режиме вебхука для хостинга Render
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()