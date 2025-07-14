import os
import asyncio
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ... (весь остальной код конфигурации и функций остается прежним, 
# но я привожу его целиком для простоты, т.к. изменились импорты и сигнатуры функций)

# 1. КОНФИГУРАЦИЯ
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)
MODEL_NAME = "gemini-1.5-flash-latest"

# ... (остальная конфигурация)
KNOWLEDGE_BASE = ""
try:
    with open('bankruptcy_law.md', 'r', encoding='utf-8') as f:
        BANKRUPTCY_CONTEXT = f.read()
    with open('interviews.md', 'r', encoding='utf-8') as f:
        INTERVIEWS_CONTEXT = f.read()
    KNOWLEDGE_BASE = BANKRUPTCY_CONTEXT + "\n\n" + INTERVIEWS_CONTEXT
    print("База знаний успешно загружена.")
except FileNotFoundError:
    print("Внимание: Файлы с базой знаний не найдены.")

# 2. ФУНКЦИИ-ОБРАБОТЧИКИ
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Здравствуйте! Я ваш юридический AI-ассистент. Задайте мне вопрос.')

def get_ai_response(question: str) -> str:
    # ... (эта функция не меняется)
    system_prompt = (
        "Твоя роль — первоклассный юридический помощник. Твое имя — Вячеслав. "
        # ... (остальной промпт)
    )
    full_prompt = f"{system_prompt}\n\n...{KNOWLEDGE_BASE}\n\n...{question}"
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(full_prompt)
    return response.text

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_question = update.message.text
    await update.message.reply_text("Думаю над вашим вопросом...") 
    
    # Запускаем get_ai_response асинхронно, чтобы не блокировать бота
    loop = asyncio.get_running_loop()
    ai_answer = await loop.run_in_executor(None, get_ai_response, user_question)
    
    cleaned_answer = ai_answer.replace('<p>', '').replace('</p>', '')
    while '\n\n\n' in cleaned_answer:
        cleaned_answer = cleaned_answer.replace('\n\n\n', '\n\n')
    
    await update.message.reply_text(cleaned_answer, parse_mode='HTML')

# 3. ОСНОВНАЯ ЧАСТЬ
def main() -> None:
    """Запускает бота."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен и работает...")
    application.run_polling()

if __name__ == '__main__':
    main()