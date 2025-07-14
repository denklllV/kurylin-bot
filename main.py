import os
import asyncio
import logging
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 1. КОНФИГУРАЦИЯ И НАСТРОЙКА
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
# Render предоставит порт, на котором нужно запуститься
PORT = int(os.environ.get('PORT', 8443))
# Render предоставит URL нашего сервиса
WEBHOOK_URL = f"https://{os.getenv('RENDER_SERVICE_NAME')}.onrender.com/{TELEGRAM_TOKEN}"

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

# 2. ФУНКЦИИ-ОБРАБОТЧИКИ БОТА
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Здравствуйте! Я ваш юридический AI-ассистент. Задайте мне вопрос.')

def get_ai_response(question: str) -> str:
    # ПОЛНАЯ ВЕРСИЯ ВАШЕГО ПРОМПТА
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
    user_question = update.message.text
    await update.message.reply_text("Думаю над вашим вопросом...")
    loop = asyncio.get_running_loop()
    ai_answer = await loop.run_in_executor(None, get_ai_response, user_question)
    cleaned_answer = ai_answer.replace('<p>', '').replace('</p>', '')
    while '\n\n\n' in cleaned_answer:
        cleaned_answer = cleaned_answer.replace('\n\n\n', '\n\n')
    try:
        await update.message.reply_text(cleaned_answer, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка форматирования HTML: {e}")
        await update.message.reply_text(cleaned_answer)

# 3. ОСНОВНАЯ ЧАСТЬ - ЗАПУСК В РЕЖИМЕ ВЕБХУКА
def main() -> None:
    """Запускает бота в режиме вебхука."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота, но не через polling, а через встроенный веб-сервер
    logger.info(f"Запуск бота на порту {PORT}. Вебхук будет установлен на {WEBHOOK_URL}")
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()