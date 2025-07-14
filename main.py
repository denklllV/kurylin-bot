import os
import asyncio
import logging
from flask import Flask, request, Response
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
PORT = int(os.environ.get('PORT', 8443))

genai.configure(api_key=GOOGLE_API_KEY)
MODEL_NAME = "gemini-1.5-flash-latest"
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
    # ... (эта функция остается без изменений)
    system_prompt = (
        "Твоя роль — первоклассный юридический помощник..." # и так далее
    )
    full_prompt = f"{system_prompt}\n\n...{KNOWLEDGE_BASE}\n\n...{question}"
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        logger.error(f"Ошибка при обращении к Google AI: {e}")
        return "К сожалению, произошла ошибка..."

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


# 3. ОСНОВНАЯ ЧАСТЬ - ЗАПУСК ВЕБ-СЕРВЕРА
if __name__ == "__main__":
    ptb_app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Регистрируем обработчики
    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Создаем веб-сервер Flask
    flask_app = Flask(__name__)

    @flask_app.route('/')
    def index():
        return "Bot is running!", 200

    @flask_app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
    async def webhook():
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, ptb_app.bot)
        await ptb_app.process_update(update)
        return Response(status=200)

    # Запускаем веб-сервер
    from waitress import serve
    logger.info(f"Запуск сервера на порту {PORT}...")
    serve(flask_app, host='0.0.0.0', port=PORT)