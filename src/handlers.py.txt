# src/handlers.py
import asyncio
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

# Импортируем всё необходимое из наших модулей
from .config import logger, MANAGER_CHAT_ID
from .config import GET_NAME, GET_DEBT, GET_INCOME, GET_REGION
from .database import save_user_to_db, save_lead_to_db
from .bot_keyboards import main_keyboard, cancel_keyboard
from .ai_logic import get_ai_response

# --- Вспомогательные функции ---

async def send_notification_to_manager(context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """Отправляет уведомление менеджеру. Централизованная функция."""
    if not MANAGER_CHAT_ID:
        logger.warning("Переменная MANAGER_CHAT_ID не установлена. Уведомление не будет отправлено.")
        return
    try:
        await context.bot.send_message(
            chat_id=MANAGER_CHAT_ID,
            text=message_text,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Уведомление успешно отправлено в чат {MANAGER_CHAT_ID}.")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление в чат {MANAGER_CHAT_ID}: {e}")

# --- Основные обработчики команд и сообщений ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start. Сохраняет пользователя и отправляет приветствие."""
    user = update.effective_user
    # Вызываем функцию сохранения пользователя из модуля database
    save_user_to_db(user_id=user.id, username=user.username, first_name=user.first_name)
    await update.message.reply_text(
        'Здравствуйте! Я ваш юридический AI-ассистент.\n\n'
        '📝 Чтобы начать анкетирование, нажмите кнопку ниже.\n'
        '❓ Чтобы задать вопрос, просто напишите его в этот чат.',
        reply_markup=main_keyboard # Используем клавиатуру из модуля bot_keyboards
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений (вопросов к AI)."""
    user_question = update.message.text
    await update.message.reply_text("Ищу ответ в базе знаний...")
    
    # Чтобы не блокировать бота, запускаем тяжелую операцию AI в отдельном потоке
    loop = asyncio.get_running_loop()
    ai_answer = await loop.run_in_executor(None, get_ai_response, user_question)
    
    # Очистка ответа от лишних тегов и переносов строк
    cleaned_answer = ai_answer.replace('<p>', '').replace('</p>', '')
    while '\n\n\n' in cleaned_answer:
        cleaned_answer = cleaned_answer.replace('\n\n\n', '\n\n')
            
    try:
        await update.message.reply_text(
            cleaned_answer,
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка форматирования HTML: {e}. Отправка без форматирования.")
        await update.message.reply_text(cleaned_answer, reply_markup=main_keyboard)

async def contact_human(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает кнопку 'Связаться с человеком'."""
    user = update.effective_user
    message_for_manager = f"<b>🧑‍💼 Запрос на связь от @{user.username} (ID: {user.id})</b>\n\nПожалуйста, свяжитесь с этим пользователем."
    await send_notification_to_manager(context, message_for_manager)
    await update.message.reply_text(
        "Ваш запрос отправлен менеджеру. Он скоро с вами свяжется.",
        reply_markup=main_keyboard
    )

# --- Логика анкеты (ConversationHandler) ---

async def start_form(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало диалога сбора анкеты."""
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
    """Последний шаг анкеты. Сохраняет данные и уведомляет менеджера."""
    context.user_data['region'] = update.message.text
    user = update.effective_user
    user_info = context.user_data
    
    summary_for_manager = (
        f"<b>✅ Новая анкета от пользователя @{user.username} (ID: {user.id})</b>\n\n"
        f"<b>Имя:</b> {user_info.get('name', '-')}\n"
        f"<b>Сумма долга:</b> {user_info.get('debt', '-')}\n"
        f"<b>Источник дохода:</b> {user_info.get('income', '-')}\n"
        f"<b>Регион:</b> {user_info.get('region', '-')}"
    )
    
    # Вызываем функции сохранения и уведомления
    save_lead_to_db(user_id=user.id, lead_data=user_info)
    await send_notification_to_manager(context, summary_for_manager)

    await update.message.reply_text(
        "Спасибо за ваши ответы! Наши специалисты скоро свяжутся с вами.",
        reply_markup=main_keyboard
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик отмены анкеты."""
    await update.message.reply_text("Заполнение анкеты отменено.", reply_markup=main_keyboard)
    context.user_data.clear()
    return ConversationHandler.END