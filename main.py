import os
import asyncio
import logging
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 1. КОНФИГУРАЦИЯ И НАСТРОЙКА
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Настройки окружения ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
PORT = int(os.environ.get('PORT', 8443))
WEBHOOK_URL = f"https://{os.getenv('RENDER_SERVICE_NAME')}.onrender.com/{TELEGRAM_TOKEN}"

# --- Настройка AI-клиента ---
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)
MODEL_NAME = "mistralai/mistral-7b-instruct:free"

# --- Загрузка базы знаний ---
KNOWLEDGE_BASE = ""
try:
    with open('bankruptcy_law.md', 'r', encoding='utf-8') as f:
        BANKRUPTCY_CONTEXT = f.read()
    with open('interviews.md', 'r', encoding='utf-8') as f:
        INTERVIEWS_CONTEXT = f.read()
    KNOWLEDGE_BASE = BANKRUPTCY_CONTEXT + "\n\n" + INTERVIEWS_CONTEXT
    logger.info(f"База знаний успешно загружена. Размер: {len(KNOWLEDGE_BASE)} символов.")
except FileNotFoundError:
    logger.warning("Внимание: Файлы с базой знаний не найдены.")

# 2. НОВЫЕ И ОБНОВЛЕННЫЕ ФУНКЦИИ
def find_relevant_chunks(question: str, knowledge_base: str, max_chunks=5) -> str:
    """
    Находит самые релевантные части из базы знаний по вопросу пользователя.
    Это самый простой способ реализовать Retrieval-Augmented Generation (RAG).
    """
    # Разбиваем базу знаний на "чанки" (абзацы)
    chunks = knowledge_base.split('\n\n')
    # Упрощаем вопрос до набора ключевых слов
    question_keywords = set(question.lower().split())

    # Оцениваем каждый чанк по количеству совпадений ключевых слов
    scored_chunks = []
    for chunk in chunks:
        chunk_words = set(chunk.lower().split())
        score = len(question_keywords.intersection(chunk_words))
        if score > 0:
            scored_chunks.append((score, chunk))
    
    # Сортируем чанки по релевантности (от большей к меньшей)
    scored_chunks.sort(reverse=True, key=lambda x: x[0])
    
    # Выбираем лучшие N чанков
    top_chunks = [chunk for score, chunk in scored_chunks[:max_chunks]]
    
    logger.info(f"Найдено {len(top_chunks)} релевантных чанков для вопроса.")
    
    # Соединяем лучшие чанки в единый контекст
    return "\n\n".join(top_chunks)

def get_ai_response(question: str) -> str:
    """
    Формирует промпт с динамическим контекстом и получает ответ от модели.
    """
    # ШАГ 1: Найти релевантную информацию в базе знаний
    dynamic_context = find_relevant_chunks(question, KNOWLEDGE_BASE)

    system_prompt = (
        "Твоя роль — первоклассный юридический помощник. Твое имя — Вячеслав. "
        "Твоя речь — человечная, мягкая и эмпатичная. "
        "Твоя задача — кратко и в общих чертах разъяснять сложные юридические вопросы, донося только самую важную суть. "
        "Отвечай ТОЛЬКО на основе предоставленной ниже 'Базы знаний'. Если в ней нет ответа, вежливо сообщи, что не обладаешь этой информацией."
        "**СТРОГИЕ ПРАВИЛА:**"
        "1. **Краткость:** Твой ответ должен быть очень коротким, в идеале 1-2 абзаца."
        "2. **Никогда не представляйся**, если тебя не спросили напрямую 'Как тебя зовут?'. Сразу переходи к сути ответа."
        "3. **Никогда не упоминай** слова 'контекст' или 'база знаний'. Отвечай так, будто эта информация — твои собственные знания."
        "4. **Для форматирования** используй теги HTML: <b>...</b> для жирного, <i>...</i> для курсива. Для создания абзаца используй ОДНУ пустую строку."
    )
    
    # ШАГ 2: Сформировать компактный промпт с найденной информацией
    user_prompt = f"База знаний:\n{dynamic_context}\n\nВопрос клиента: {question}"

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Ошибка при обращении к OpenRouter AI: {e}")
        return "К сожалению, произошла ошибка при обрашении к AI-сервису. Попробуйте позже."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение при команде /start."""
    await update.message.reply_text('Здравствуйте! Я ваш юридический AI-ассистент. Задайте мне вопрос.')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает текстовые сообщения от пользователя."""
    user_question = update.message.text
    await update.message.reply_text("Ищу ответ в базе знаний...")
    
    loop = asyncio.get_running_loop()
    ai_answer = await loop.run_in_executor(None, get_ai_response, user_question)
    
    cleaned_answer = ai_answer.replace('<p>', '').replace('</p>', '')
    while '\n\n\n' in cleaned_answer:
        cleaned_answer = cleaned_answer.replace('\n\n\n', '\n\n')
        
    try:
        await update.message.reply_text(cleaned_answer, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка форматирования HTML: {e}. Отправка без форматирования.")
        await update.message.reply_text(cleaned_answer)

# 3. ОСНОВНАЯ ЧАСТЬ - ЗАПУСК В РЕЖИМЕ ВЕБХУКА
def main() -> None:
    """Запускает бота в режиме вебхука."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info(f"Запуск бота на порту {PORT}. Вебхук будет установлен на {WEBHOOK_URL}")
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()