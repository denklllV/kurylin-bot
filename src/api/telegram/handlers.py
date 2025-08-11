# START OF FILE: src/api/telegram/handlers.py

import io
import json
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode, ChatAction
from pydub import AudioSegment

from src.app.services.ai_service import AIService
from src.app.services.lead_service import LeadService
# ИЗМЕНЕНИЕ: Импортируем новый сервис
from src.app.services.analytics_service import AnalyticsService
from src.domain.models import User, Message
from src.api.telegram.keyboards import main_keyboard, cancel_keyboard
from src.shared.logger import logger
from src.shared.config import GET_NAME, GET_DEBT, GET_INCOME, GET_REGION, MANAGER_CHAT_ID

# --- HELPER FUNCTION ---
async def _process_and_send_response(update: Update, context: ContextTypes.DEFAULT_TYPE, user_question: str):
    """Общий код для обработки текстового запроса и отправки ответа."""
    ai_service: AIService = context.bot_data['ai_service']
    user_id = update.effective_user.id
    
    ai_service.repo.save_message(user_id, Message(role='user', content=user_question))
    await update.message.reply_chat_action(ChatAction.TYPING)

    # Пока RAG не работает, мы не можем его вызывать
    # response_text, debug_info = ai_service.get_text_response(user_id, user_question)
    
    # Временная заглушка, пока RAG чинится
    response_text = "Принял ваш вопрос. В данный момент функция ответов временно отключена на техническое обслуживание. Пожалуйста, воспользуйтесь анкетой."
    debug_info = {}

    context.bot_data['last_debug_info'] = debug_info
    
    ai_service.repo.save_message(user_id, Message(role='assistant', content=response_text))
    await update.message.reply_text(response_text, parse_mode=ParseMode.HTML, reply_markup=main_keyboard)

# --- USER-FACING HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lead_service: LeadService = context.bot_data['lead_service']
    user_data = update.effective_user
    utm_source = context.args[0] if context.args else None
    
    user = User(
        id=user_data.id,
        username=user_data.username,
        first_name=user_data.first_name,
        utm_source=utm_source
    )
    # ИСПРАВЛЕНИЕ: Используем корректный метод сохранения, который есть в репозитории
    lead_service.repo.save_user(user)

    await update.message.reply_text(
        'Здравствуйте! Я ваш юридический AI-ассистент.\n\n'
        '📝 Чтобы начать анкету, нажмите кнопку ниже.\n'
        '❓ Чтобы задать вопрос, просто напишите его в этот чат.',
        reply_markup=main_keyboard
    )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Пока RAG не работает, временно отключаем
    # await _process_and_send_response(update, context, update.message.text)
    await update.message.reply_text("Функция ответов на вопросы временно на техобслуживании. Пожалуйста, воспользуйтесь анкетой или свяжитесь с менеджером.", reply_markup=main_keyboard)


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Пока RAG не работает, временно отключаем
    # ai_service: AIService = context.bot_data['ai_service']
    # ... (весь код обработки голоса)
    await update.message.reply_text("Функция ответов на вопросы временно на техобслуживании. Пожалуйста, воспользуйтесь анкетой или свяжитесь с менеджером.", reply_markup=main_keyboard)


async def contact_human(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = f"@{user.username}" if user.username else f"ID: {user.id}"
    message_for_manager = f"<b>🧑‍💼 Запрос на связь от {username}</b>\n\nПожалуйста, свяжитесь с этим пользователем."
    if MANAGER_CHAT_ID:
        await context.bot.send_message(chat_id=MANAGER_CHAT_ID, text=message_for_manager, parse_mode=ParseMode.HTML)
    await update.message.reply_text("Ваш запрос отправлен менеджеру.", reply_markup=main_keyboard)

# --- ADMIN DEBUG HANDLERS ---
def is_admin(update: Update) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return str(update.effective_user.id) == MANAGER_CHAT_ID

async def last_answer_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /last_answer для маркетолога."""
    if not is_admin(update):
        return
    # ... (код без изменений) ...
    debug_info = context.bot_data.get('last_debug_info')
    if not debug_info:
        await update.message.reply_text("Отладочная информация еще не была записана.")
        return
    # ... (остальной код) ...

# НОВЫЙ ОБРАБОТЧИК ДЛЯ АНАЛИТИКИ
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats для получения аналитического отчета."""
    if not is_admin(update):
        return

    await update.message.reply_text("Собираю статистику, это может занять несколько секунд...")
    
    analytics_service: AnalyticsService = context.bot_data['analytics_service']
    report = analytics_service.generate_summary_report()
    
    await update.message.reply_text(report, parse_mode=ParseMode.HTML)


async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /health_check для технического специалиста."""
    # ... (код без изменений) ...

# --- Логика анкеты (без изменений) ---
async def start_form(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ...
    return GET_NAME
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ...
    return GET_DEBT
async def get_debt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ...
    return GET_INCOME
async def get_income(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ...
    return GET_REGION
async def get_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lead_service: LeadService = context.bot_data['lead_service']
    user_data = update.effective_user
    context.user_data['region'] = update.message.text
    user = User(id=user_data.id, username=user_data.username, first_name=user_data.first_name)
    await lead_service.save_lead(user, context.user_data)
    await update.message.reply_text("Спасибо за ваши ответы! Наши специалисты скоро свяжутся с вами.", reply_markup=main_keyboard)
    context.user_data.clear()
    return ConversationHandler.END
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ...
    return ConversationHandler.END

# END OF FILE: src/api/telegram/handlers.py