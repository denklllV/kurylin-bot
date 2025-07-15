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
from supabase import create_client, Client

# 1. КОНФИГУРАЦИЯ И НАСТРОЙКА
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Настройки окружения ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
PORT = int(os.environ.get('PORT', 8443))
WEBHOOK_URL = f"https://{os.getenv('RENDER_SERVICE_NAME')}.onrender.com/{TELEGRAM_TOKEN}"
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
# НОВАЯ ПЕРЕМЕННАЯ ДЛЯ УВЕДОМЛЕНИЙ
MANAGER_CHAT_ID = os.getenv('MANAGER_CHAT_ID')

# --- Клиенты сервисов ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
MODEL_NAME = "mistralai/mistral-7b-instruct:free"

# ... (Загрузка базы знаний, Состояния, Клавиатуры - без изменений)
KNOWLEDGE_BASE = ""
try:
    with open('bankruptcy_law.md', 'r', encoding='utf-8') as f: BANKRUPTCY_CONTEXT = f.read()
    with open('interviews.md', 'r', encoding='utf-8') as f: INTERVIEWS_CONTEXT = f.read()
    KNOWLEDGE_BASE = BANKRUPTCY_CONTEXT + "\n\n" + INTERVIEWS_CONTEXT
except FileNotFoundError: logger.warning("Внимание: Файлы с базой знаний не найдены.")
GET_NAME, GET_DEBT, GET_INCOME, GET_REGION = range(4)
main_keyboard = ReplyKeyboardMarkup([['📝 Заполнить анкету', '🧑‍💼 Связаться с человеком']], resize_keyboard=True)
cancel_keyboard = ReplyKeyboardMarkup([['Отмена']], resize_keyboard=True)


# 2. ФУНКЦИИ-ОБРАБОТЧИКИ БОТА

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    try:
        supabase.table('users').upsert({'user_id': user.id, 'username': user.username, 'first_name': user.first_name}).execute()
        logger.info(f"Пользователь {user.id} сохранен или обновлен в БД.")
    except Exception as e:
        logger.error(f"Ошибка при сохранении пользователя {user.id} в Supabase: {e}")
    await update.message.reply_text(
        'Здравствуйте! Я ваш юридический AI-ассистент.\n\n'
        '📝 Чтобы начать анкетирование, нажмите кнопку ниже.\n'
        '❓ Чтобы задать вопрос, просто напишите его в этот чат.',
        reply_markup=main_keyboard
    )

# --- НОВЫЕ И ОБНОВЛЕННЫЕ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def save_lead_to_database(user_id: int, lead_data: dict):
    # ... (без изменений)
    try:
        data_to_insert = {'user_id': user_id, 'name': lead_data.get('name'), 'debt_amount': lead_data.get('debt'), 'income_source': lead_data.get('income'), 'region': lead_data.get('region')}
        supabase.table('leads').insert(data_to_insert).execute()
        logger.info(f"Анкета для пользователя {user_id} успешно сохранена в БД.")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении анкеты для {user_id} в Supabase: {e}")
        return False

async def send_notification_to_manager(context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """ОТПРАВЛЯЕТ УВЕДОМЛЕНИЕ МЕНЕДЖЕРУ В ЛИЧНЫЙ ЧАТ."""
    if not MANAGER_CHAT_ID:
        logger.warning("Переменная MANAGER_CHAT_ID не установлена. Уведомление не будет отправлено.")
        return
    try:
        await context.bot.send_message(chat_id=MANAGER_CHAT_ID, text=message_text, parse_mode='HTML')
        logger.info(f"Уведомление успешно отправлено в чат {MANAGER_CHAT_ID}.")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление в чат {MANAGER_CHAT_ID}: {e}")

# --- ЛОГИКА АНКЕТИРОВАНИЯ ---

# ... (start_form, get_name, get_debt, get_income - без изменений)
async def start_form(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отлично! Приступаем к заполнению анкеты.\n\nКак я могу к вам обращаться?", reply_markup=cancel_keyboard)
    return GET_NAME
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Какая у вас общая сумма задолженности?", reply_markup=cancel_keyboard)
    return GET_DEBT
async def get_debt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['debt'] = update.message.text
    await update.message.reply_text("Укажите ваш основной источник дохода.", reply_markup=cancel_keyboard)
    return GET_INCOME
async def get_income(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['income'] = update.message.text
    await update.message.reply_text("В каком регионе (область, край) вы прописаны?", reply_markup=cancel_keyboard)
    return GET_REGION

async def get_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Завершает анкету, сохраняет данные, ОТПРАВЛЯЕТ РЕАЛЬНОЕ УВЕДОМЛЕНИЕ."""
    context.user_data['region'] = update.message.text
    user = update.effective_user
    user_info = context.user_data
    
    # Формируем текст уведомления для менеджера
    summary_for_manager = (
        f"<b>✅ Новая анкета от пользователя @{user.username} (ID: {user.id})</b>\n\n"
        f"<b>Имя:</b> {user_info.get('name', '-')}\n"
        f"<b>Сумма долга:</b> {user_info.get('debt', '-')}\n"
        f"<b>Источник дохода:</b> {user_info.get('income', '-')}\n"
        f"<b>Регион:</b> {user_info.get('region', '-')}"
    )
    
    # ШАГ 1: Сохраняем в БД
    save_lead_to_database(user_id=user.id, lead_data=user_info)

    # ШАГ 2: Отправляем реальное уведомление
    await send_notification_to_manager(context, summary_for_manager)

    # ШАГ 3: Отвечаем пользователю
    await update.message.reply_text("Спасибо за ваши ответы! Наши специалисты скоро свяжутся с вами.", reply_markup=main_keyboard)
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Заполнение анкеты отменено.", reply_markup=main_keyboard)
    context.user_data.clear()
    return ConversationHandler.END

async def contact_human(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает кнопку 'Связаться с человеком', отправляя уведомление."""
    user = update.effective_user
    message_for_manager = f"<b>🧑‍💼 Запрос на связь от @{user.username} (ID: {user.id})</b>\n\nПожалуйста, свяжитесь с этим пользователем."
    # Используем ту же функцию уведомлений
    await send_notification_to_manager(context, message_for_manager)
    await update.message.reply_text("Ваш запрос отправлен менеджеру. Он скоро с вами свяжется.", reply_markup=main_keyboard)


# ... (handle_message и main без ключевых изменений)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_question = update.message.text
    await update.message.reply_text("Ищу ответ в базе знаний...")
    loop = asyncio.get_running_loop()
    ai_answer = await loop.run_in_executor(None, get_ai_response, user_question)
    cleaned_answer = ai_answer.replace('<p>', '').replace('</p>', '')
    while '\n\n\n' in cleaned_answer: cleaned_answer = cleaned_answer.replace('\n\n\n', '\n\n')
    try:
        await update.message.reply_text(cleaned_answer, parse_mode='HTML', reply_markup=main_keyboard)
    except Exception as e:
        logger.error(f"Ошибка форматирования HTML: {e}. Отправка без форматирования.")
        await update.message.reply_text(cleaned_answer, reply_markup=main_keyboard)

def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    form_button_filter = filters.Regex('^📝 Заполнить анкету$')
    contact_button_filter = filters.Regex('^🧑‍💼 Связаться с человеком$')
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(form_button_filter, start_form)],
        states={
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^Отмена$'), get_name)],
            GET_DEBT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^Отмена$'), get_debt)],
            GET_INCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^Отмена$'), get_income)],
            GET_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex('^Отмена$'), get_region)],
        },
        fallbacks=[CommandHandler('cancel', cancel), MessageHandler(filters.Regex('^Отмена$'), cancel)],
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(contact_button_filter, contact_human))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~form_button_filter & ~contact_button_filter, handle_message))
    logger.info(f"Запуск бота на порту {PORT}.")
    application.run_webhook(listen="0.0.0.0", port=PORT, url_path=TELEGRAM_TOKEN, webhook_url=WEBHOOK_URL)


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ AI (без изменений) ---
def find_relevant_chunks(question: str, knowledge_base: str, max_chunks=5) -> str:
    chunks = knowledge_base.split('\n\n')
    question_keywords = set(question.lower().split())
    scored_chunks = []
    for chunk in chunks:
        chunk_words = set(chunk.lower().split())
        score = len(question_keywords.intersection(chunk_words))
        if score > 0: scored_chunks.append((score, chunk))
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
        completion = client.chat.completions.create(model=MODEL_NAME, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}])
        return completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Ошибка при обращении к OpenRouter AI: {e}")
        return "К сожалению, произошла ошибка при обрашении к AI-сервису. Попробуйте позже."

if __name__ == "__main__":
    main()