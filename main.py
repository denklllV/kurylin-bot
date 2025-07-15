import os
import asyncio
import logging
from openai import OpenAI
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# 1. КОНФИГУРАЦИЯ И НАСТРОЙКА
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
PORT = int(os.environ.get('PORT', 8443))
WEBHOOK_URL = f"https://{os.getenv('RENDER_SERVICE_NAME')}.onrender.com/{TELEGRAM_TOKEN}"
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
MODEL_NAME = "mistralai/mistral-7b-instruct:free"
KNOWLEDGE_BASE = ""
try:
    with open('bankruptcy_law.md', 'r', encoding='utf-8') as f:
        BANKRUPTCY_CONTEXT = f.read()
    with open('interviews.md', 'r', encoding='utf-8') as f:
        INTERVIEWS_CONTEXT = f.read()
    KNOWLEDGE_BASE = BANKRUPTCY_CONTEXT + "\n\n" + INTERVIEWS_CONTEXT
    logger.info(f"База знаний успешно загружена.")
except FileNotFoundError:
    logger.warning("Внимание: Файлы с базой знаний не найдены.")

# --- Состояния для ConversationHandler ---
GET_NAME, GET_DEBT, GET_INCOME, GET_REGION = range(4)

# --- НОВАЯ ПОСТОЯННАЯ КЛАВИАТУРА ---
main_keyboard = ReplyKeyboardMarkup(
    [['📝 Заполнить анкету', '🧑‍💼 Связаться с человеком']], 
    resize_keyboard=True
)
cancel_keyboard = ReplyKeyboardMarkup([['Отмена']], resize_keyboard=True)

# 2. ФУНКЦИИ-ОБРАБОТЧИКИ БОТА

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение и показывает постоянную клавиатуру."""
    await update.message.reply_text(
        'Здравствуйте! Я ваш юридический AI-ассистент.\n\n'
        '📝 Чтобы начать анкетирование, нажмите соответствующую кнопку ниже.\n'
        '❓ Чтобы задать вопрос, просто напишите его в этот чат.',
        reply_markup=main_keyboard
    )

# --- ЛОГИКА АНКЕТИРОВАНИЯ (ИЗМЕНЕНА) ---

async def start_form(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает сценарий анкетирования, запрашивая имя."""
    await update.message.reply_text(
        "Отлично! Приступаем к заполнению анкеты.\n\n"
        "Как я могу к вам обращаться?",
        reply_markup=cancel_keyboard
    )
    return GET_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    await update.message.reply_text(f"Приятно познакомиться! Какая у вас общая сумма задолженности?", reply_markup=cancel_keyboard)
    return GET_DEBT

async def get_debt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['debt'] = update.message.text
    await update.message.reply_text("Понятно. Укажите ваш основной источник дохода (например, 'Работаю по ТК РФ', 'Пенсионер', 'Безработный').", reply_markup=cancel_keyboard)
    return GET_INCOME

async def get_income(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['income'] = update.message.text
    await update.message.reply_text("Спасибо. И последний вопрос: в каком регионе (область, край) вы прописаны?", reply_markup=cancel_keyboard)
    return GET_REGION

async def get_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['region'] = update.message.text
    user_info = context.user_data
    summary = (
        f"<b>Спасибо за ваши ответы!</b>\n\n"
        f"Проверьте, пожалуйста, все ли верно:\n"
        f"- <b>Имя:</b> {user_info.get('name', 'не указано')}\n"
        f"- <b>Сумма долга:</b> {user_info.get('debt', 'не указано')}\n"
        f"- <b>Источник дохода:</b> {user_info.get('income', 'не указано')}\n"
        f"- <b>Регион:</b> {user_info.get('region', 'не указано')}\n\n"
        f"Наши специалисты скоро свяжутся с вами."
    )
    # Возвращаем главную клавиатуру после завершения анкеты
    await update.message.reply_text(summary, parse_mode='HTML', reply_markup=main_keyboard)
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет анкету и возвращает главную клавиатуру."""
    await update.message.reply_text("Заполнение анкеты отменено.", reply_markup=main_keyboard)
    context.user_data.clear()
    return ConversationHandler.END

async def contact_human(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает кнопку 'Связаться с человеком'."""
    await update.message.reply_text("Вы выбрали 'Связаться с человеком'. Этот функционал в разработке.", reply_markup=main_keyboard)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает любой текст как вопрос к AI."""
    user_question = update.message.text
    await update.message.reply_text("Ищу ответ в базе знаний...")
    loop = asyncio.get_running_loop()
    ai_answer = await loop.run_in_executor(None, get_ai_response, user_question)
    cleaned_answer = ai_answer.replace('<p>', '').replace('</p>', '')
    while '\n\n\n' in cleaned_answer:
        cleaned_answer = cleaned_answer.replace('\n\n\n', '\n\n')
    try:
        await update.message.reply_text(cleaned_answer, parse_mode='HTML', reply_markup=main_keyboard)
    except Exception as e:
        logger.error(f"Ошибка форматирования HTML: {e}. Отправка без форматирования.")
        await update.message.reply_text(cleaned_answer, reply_markup=main_keyboard)

# 3. ОСНОВНАЯ ЧАСТЬ - ЗАПУСК И РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ
def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # --- ФИЛЬТРЫ ДЛЯ КНОПОК ГЛАВНОГО МЕНЮ ---
    form_button_filter = filters.Regex('^📝 Заполнить анкету$')
    contact_button_filter = filters.Regex('^🧑‍💼 Связаться с человеком$')
    
    # --- ОБРАБОТЧИК СЦЕНАРИЯ АНКЕТИРОВАНИЯ ---
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(form_button_filter, start_form)],
        states={
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^Отмена$'), get_name)],
            GET_DEBT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^Отмена$'), get_debt)],
            GET_INCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^Отмена$'), get_income)],
            GET_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^Отмена$'), get_region)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            MessageHandler(filters.Regex('^Отмена$'), cancel)
        ],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(contact_button_filter, contact_human))

    # Обработчик для всех остальных текстовых сообщений (вопросы к AI)
    # Он должен стоять последним и игнорировать тексты кнопок
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~form_button_filter & ~contact_button_filter, 
        handle_message
    ))
    
    logger.info(f"Запуск бота на порту {PORT}.")
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=WEBHOOK_URL
    )

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (без изменений) ---
def find_relevant_chunks(question: str, knowledge_base: str, max_chunks=5) -> str:
    chunks = knowledge_base.split('\n\n')
    question_keywords = set(question.lower().split())
    scored_chunks = []
    for chunk in chunks:
        chunk_words = set(chunk.lower().split())
        score = len(question_keywords.intersection(chunk_words))
        if score > 0:
            scored_chunks.append((score, chunk))
    scored_chunks.sort(reverse=True, key=lambda x: x[0])
    top_chunks = [chunk for score, chunk in scored_chunks[:max_chunks]]
    return "\n\n".join(top_chunks)

def get_ai_response(question: str) -> str:
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

if __name__ == "__main__":
    main()