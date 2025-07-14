import os
import asyncio
import logging
import google.generativeai as genai
from flask import Flask, request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 1. КОНФИГУРАЦИЯ И НАСТРОЙКА
# Включаем логирование, чтобы видеть, что происходит
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем переменные окружения
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
# Render предоставит нам URL нашего сервиса. Если запускаем локально, можно задать свой.
RENDER_URL = os.getenv('RENDER_URL')
WEBHOOK_URL = f"{RENDER_URL}/{TELEGRAM_TOKEN}"
# Render предоставит порт, на котором нужно запуститься
PORT = int(os.environ.get('PORT', 8443))

# Настраиваем AI
genai.configure(api_key=GOOGLE_API_KEY)
MODEL_NAME = "gemini-1.5-flash-latest"

# Загружаем базу знаний
KNOWLEDGE_BASE = ""
try:
    with open('bankruptcy_law.md', 'r', encoding='utf-8') as f:
        BANKRUPTCY_CONTEXT = f.read()
    with open('interviews.md', 'r', encoding='utf-8') as f:
        INTERVIEWS_CONTEXT = f.read()
    KNOWLEDGE_BASE = BANKRUPTCY_CONTEXT + "\n\n" + INTERVIEWS_CONTEXT
    logger.info("База знаний успешно загружена.")
except FileNotFoundError:
    logger.warning("Внимание: Файлы с базой знаний не найдены.")

# 2. ФУНКЦИИ-ОБРАБОТЧИКИ БОТА (логика та же, но теперь они 'async')
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /start."""
    await update.message.reply_text('Здравствуйте! Я ваш юридический AI-ассистент. Задайте мне вопрос.')

def get_ai_response(question: str) -> str:
    """Синхронная функция для получения ответа от AI."""
    system_prompt = (
        "Твоя роль — первоклассный юридический помощник. Твое имя — Вячеслав. "
        "Твоя речь — человечная, мягкая и эмпатичная. "
        "Твоя задача — кратко и в общих чертах разъяснять сложные юридические вопросы, донося только самую важную суть."
        "**СТРОГИЕ ПРАВИЛА:**"
        "1. **Краткость:** Твой ответ должен быть сжатым, в идеале 2-3 абзаца. Не углубляйся в детали без необходимости."
        "2. **Никогда не представляйся**, если тебя не спросили напрямую 'Как тебя зовут?'. Сразу переходи к сути ответа."
        "3. **Никогда не упоминай** слова 'контекст' или 'предоставленная информация'. Отвечай так, будто эта информация — твои собственные знания."
        "4. **Для форматирования** используй теги HTML: <b>...</b> для жирного, <i>...</i> для курсива. Для создания абзаца используй ОДНУ пустую строку."
    )
    full_prompt = f"{system_prompt}\n\nВот база знаний для твоего ответа:\n{KNOWLEDGE_BASE}\n\nВопрос клиента: {question}"
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        logger.error(f"Ошибка при обращении к Google AI: {e}")
        return "К сожалению, произошла ошибка при обращении к AI-сервису. Попробуйте позже."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает текстовые сообщения."""
    user_question = update.message.text
    await update.message.reply_text("Думаю над вашим вопросом...")

    # Запускаем блокирующую функцию AI в отдельном потоке, чтобы не тормозить бота
    loop = asyncio.get_running_loop()
    ai_answer = await loop.run_in_executor(None, get_ai_response, user_question)

    # Очистка ответа
    cleaned_answer = ai_answer.replace('<p>', '').replace('</p>', '')
    while '\n\n\n' in cleaned_answer:
        cleaned_answer = cleaned_answer.replace('\n\n\n', '\n\n')

    try:
        await update.message.reply_text(cleaned_answer, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка форматирования HTML или другая ошибка отправки: {e}")
        await update.message.reply_text(cleaned_answer)

# 3. НАСТРОЙКА ВЕБ-СЕРВЕРА И ВЕБХУКА
def main() -> None:
    """Основная функция запуска."""
    # Создаем приложение PTB (Python Telegram Bot)
    ptb_app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Регистрируем обработчики команд
    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Создаем веб-сервер Flask
    flask_app = Flask(__name__)

    @flask_app.route('/')
    def index():
        """Пустая главная страница, чтобы Render видел, что сервис жив."""
        return "Bot is running!", 200

    @flask_app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
    async def webhook():
        """Эта функция принимает обновления от Telegram и передает их в PTB."""
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, ptb_app.bot)
        await ptb_app.process_update(update)
        return Response(status=200)

    async def setup_webhook():
        """Устанавливает вебхук при запуске, чтобы Telegram знал наш адрес."""
        logger.info(f"Установка вебхука на {WEBHOOK_URL}")
        await ptb_app.bot.set_webhook(url=WEBHOOK_URL, allowed_updates=Update.ALL_TYPES)
        logger.info("Вебхук успешно установлен")

    # Это магия для корректного запуска асинхронного кода вместе с Flask
    async def run_all():
        await setup_webhook()
        # Запускаем веб-сервер
        # waitress - это более надежный сервер, чем встроенный в Flask
        from waitress import serve
        serve(flask_app, host='0.0.0.0', port=PORT)

    logger.info("Запуск бота в режиме вебхука...")
    asyncio.run(run_all())


if __name__ == "__main__":
    main()