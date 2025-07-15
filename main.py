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
# НОВЫЙ ИМПОРТ для Supabase
from supabase import create_client, Client

# 1. КОНФИГУРАЦИЯ И НАСТРОЙКА
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Настройки окружения ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
PORT = int(os.environ.get('PORT', 8443))
WEBHOOK_URL = f"https://{os.getenv('RENDER_SERVICE_NAME')}.onrender.com/{TELEGRAM_TOKEN}"

# --- НОВЫЙ БЛОК: Настройка клиента Supabase ---
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Настройка AI-клиента ---
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
MODEL_NAME = "mistralai/mistral-7b-instruct:free"

# --- Загрузка базы знаний (без изменений) ---
KNOWLEDGE_BASE = ""
try:
    with open('bankruptcy_law.md', 'r', encoding='utf-8') as f: BANKRUPTCY_CONTEXT = f.read()
    with open('interviews.md', 'r', encoding='utf-8') as f: INTERVIEWS_CONTEXT = f.read()
    KNOWLEDGE_BASE = BANKRUPTCY_CONTEXT + "\n\n" + INTERVIEWS_CONTEXT
except FileNotFoundError:
    logger.warning("Внимание: Файлы с базой знаний не найдены.")

# --- Состояния для ConversationHandler ---
GET_NAME, GET_DEBT, GET_INCOME, GET_REGION = range(4)

# --- Клавиатуры (без изменений) ---
main_keyboard = ReplyKeyboardMarkup([['📝 Заполнить анкету', '🧑‍💼 Связаться с человеком']], resize_keyboard=True)
cancel_keyboard = ReplyKeyboardMarkup([['Отмена']], resize_keyboard=True)

# 2. ФУНКЦИИ-ОБРАБОТЧИКИ БОТА

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветствие и сохраняет пользователя в БД."""
    user = update.effective_user
    # Пытаемся сохранить информацию о пользователе при первом старте
    try:
        supabase.table('users').upsert({
            'user_id': user.id,
            'username': user.username,
            'first_name': user.first_name
        }).execute()
        logger.info(f"Пользователь {user.id} сохранен или обновлен в БД.")
    except Exception as e:
        logger.error(f"Ошибка при сохранении пользователя {user.id} в Supabase: {e}")

    await update.message.reply_text(
        'Здравствуйте! Я ваш юридический AI-ассистент.\n\n'
        '📝 Чтобы начать анкетирование, нажмите кнопку ниже.\n'
        '❓ Чтобы задать вопрос, просто напишите его в этот чат.',
        reply_markup=main_keyboard
    )

# --- НОВЫЕ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def save_lead_to_database(user_id: int, lead_data: dict):
    """Сохраняет данные анкеты в таблицу 'leads' в Supabase."""
    try:
        data_to_insert = {
            'user_id': user_id,
            'name': lead_data.get('name'),
            'debt_amount': lead_data.get('debt'),
            'income_source': lead_data.get('income'),
            'region': lead_data.get('region')
        }
        supabase.table('leads').insert(data_to_insert).execute()
        logger.info(f"Анкета для пользователя {user_id} успешно сохранена в БД.")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении анкеты для {user_id} в Supabase: {e}")
        return False

def send_notification_to_manager(summary: str):
    """Функция-заглушка для отправки уведомлений менеджеру."""
    # В будущем здесь будет реальный код отправки сообщения в Telegram-чат
    logger.info("--- УВЕДОМЛЕНИЕ МЕНЕДЖЕРУ (ЗАГЛУШКА) ---")
    logger.info(summary)
    logger.info("-----------------------------------------")


# --- ЛОГИКА АНКЕТИРОВАНИЯ (ИЗМЕНЕНА) ---

async def start_form(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает сценарий анкетирования."""
    await update.message.reply_text(
        "Отлично! Приступаем к заполнению анкеты.\n\nКак я могу к вам обращаться?",
        reply_markup=cancel_keyboard
    )
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
    """Завершает анкету, сохраняет данные, отправляет уведомление."""
    context.user_data['region'] = update.message.text
    user_info = context.user_data
    user_id = update.effective_user.id
    
    summary = (
        f"<b>Новая анкета от пользователя @{update.effective_user.username} (ID: {user_id})</b>\n\n"
        f"- <b>Имя:</b> {user_info.get('name', 'не указано')}\n"
        f"- <b>Сумма долга:</b> {user_info.get('debt', 'не указано')}\n"
        f"- <b>Источник дохода:</b> {user_info.get('income', 'не указано')}\n"
        f"- <b>Регион:</b> {user_info.get('region', 'не указано')}"
    )
    
    # ШАГ 1: Сохраняем в БД
    save_lead_to_database(user_id=user_id, lead_data=user_info)

    # ШАГ 2: Отправляем уведомление (пока в логи)
    send_notification_to_manager(summary)

    # ШАГ 3: Отвечаем пользователю
    await update.message.reply_text(
        "Спасибо за ваши ответы! Наши специалисты скоро свяжутся с вами.",
        reply_markup=main_keyboard
    )
    context.user_data.clear()
    return ConversationHandler.END

# ... (остальные функции: cancel, contact_human, handle_message, main и т.д. без ключевых изменений)
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Заполнение анкеты отменено.", reply_markup=main_keyboard)
    context.user_data.clear()
    return ConversationHandler.END

async def contact_human(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Вы выбрали 'Связаться с человеком'. Этот функционал в разработке.", reply_markup=main_keyboard)

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
    system_prompt = ("Твоя роль — первоклассный юридический помощник...") # Сокращено для краткости
    user_prompt = f"База знаний:\n{dynamic_context}\n\nВопрос клиента: {question}"
    try:
        completion = client.chat.completions.create(model=MODEL_NAME, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}])
        return completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Ошибка при обращении к OpenRouter AI: {e}")
        return "К сожалению, произошла ошибка при обрашении к AI-сервису. Попробуйте позже."

if __name__ == "__main__":
    main()