# path: src/api/telegram/user_handlers.py
import io
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, User as TelegramUser
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode, ChatAction
from telegram.error import TelegramError

from src.app.services.ai_service import AIService
from src.app.services.lead_service import LeadService
from src.domain.models import User, Message
from src.api.telegram.keyboards import get_main_keyboard, cancel_keyboard, make_quiz_keyboard
from src.shared.logger import logger
from src.shared.config import GET_NAME, GET_DEBT, GET_INCOME, GET_REGION

# --- Вспомогательные функции ---
def get_client_context(context: ContextTypes.DEFAULT_TYPE) -> (int, str):
    client_id = context.bot_data.get('client_id')
    manager_contact = context.bot_data.get('manager_contact')
    return client_id, manager_contact

# ИЗМЕНЕНИЕ: Создаем единую, переиспользуемую функцию для отправки запроса
async def _send_contact_request(user: TelegramUser, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет уведомление менеджеру о запросе на связь."""
    _, manager_contact = get_client_context(context)
    username = f"@{user.username}" if user.username else f"ID: {user.id}"
    message_for_manager = f"<b>🧑‍💼 Запрос на связь от {username}</b>\n\nПожалуйста, свяжитесь с этим пользователем."
    if manager_contact:
        await context.bot.send_message(chat_id=manager_contact, text=message_for_manager, parse_mode=ParseMode.HTML)
    
# --- Основные обработчики для пользователей ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['is_admin_mode'] = False
    
    lead_service: LeadService = context.application.bot_data['lead_service']
    user_data = update.effective_user
    client_id, _ = get_client_context(context)
    utm_source = context.args[0] if context.args else None
    user = User(id=user_data.id, username=user_data.username, first_name=user_data.first_name, utm_source=utm_source)
    lead_service.repo.save_user(user, client_id)
    
    await update.message.reply_text(
        'Здравствуйте! Я ваш юридический AI-ассистент.\n\n'
        '📝 Чтобы начать анкету, нажмите кнопку ниже.\n'
        '🎯 Пройдите чек-лист, чтобы получить точную оценку.\n'
        '❓ Чтобы задать вопрос, просто напишите его в этот чат.',
        reply_markup=get_main_keyboard(context)
    )

async def _process_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE, user_question: str):
    ai_service: AIService = context.application.bot_data['ai_service']
    user_id = update.effective_user.id
    client_id, _ = get_client_context(context)

    if context.user_data.get('is_admin_mode'):
        await update.message.reply_text("Вы находитесь в режиме администратора. Для выхода введите /start.")
        return

    ai_service.repo.save_message(user_id, Message(role='user', content=user_question), client_id)
    await update.message.reply_chat_action(ChatAction.TYPING)

    response_text, debug_info = ai_service.get_text_response(user_id, user_question, client_id)
    context.application.bot_data.setdefault('last_debug_info', {})[client_id] = debug_info
    ai_service.repo.save_message(user_id, Message(role='assistant', content=response_text), client_id)
    
    quiz_completed, _ = ai_service.repo.get_user_quiz_status(user_id, client_id)
    
    action_buttons = []
    checklist_data = context.bot_data.get('checklist_data')
    if checklist_data and not quiz_completed:
        action_buttons.append(InlineKeyboardButton("Пройти чек-лист", callback_data="start_quiz_from_prompt"))
    
    # ИЗМЕНЕНИЕ: Переименовываем кнопку
    action_buttons.append(InlineKeyboardButton("Связь с человеком", callback_data="request_human_contact"))
    
    reply_markup = InlineKeyboardMarkup([action_buttons])
    
    disclaimer = "\n\n*Важно: эта информация носит справочный характер и не является юридической консультацией.*"
    final_text = response_text + disclaimer
    
    parse_mode = ParseMode.MARKDOWN
    
    await update.message.reply_text(final_text, reply_markup=reply_markup, parse_mode=parse_mode)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _process_user_message(update, context, update.message.text)

async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (код без изменений) ...
    ai_service: AIService = context.application.bot_data['ai_service']
    await update.message.reply_text("Получил ваше голосовое, расшифровываю...")
    await update.message.reply_chat_action(ChatAction.TYPING)
    voice = update.message.voice
    voice_file = await voice.get_file()
    voice_bytes = await voice_file.download_as_bytearray()
    try:
        ogg_stream = io.BytesIO(voice_bytes)
        transcribed_text = ai_service.transcribe_voice(ogg_stream.read())
    except Exception as e:
        transcribed_text = None
    if transcribed_text:
        await update.message.reply_text(f"Ваш вопрос: «{transcribed_text}»\n\nОбрабатываю...")
        await _process_user_message(update, context, transcribed_text)
    else:
        await update.message.reply_text("К сожалению, не удалось распознать речь. Попробуйте записать снова или, пожалуйста, напишите ваш вопрос текстом.")
        return

# ИЗМЕНЕНИЕ: Обработчик для кнопки из основного меню
async def contact_human(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_contact_request(update.effective_user, context)
    await update.message.reply_text("Ваш запрос отправлен менеджеру.", reply_markup=get_main_keyboard(context))

# ИЗМЕНЕНИЕ: Обработчик для инлайн-кнопки
async def request_human_contact_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Передаю ваш запрос менеджеру...")
    # Теперь мы вызываем нашу общую функцию с правильными данными
    await _send_contact_request(query.from_user, context)

# ... (остальной код файла без изменений) ...
async def start_checklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    checklist_data = context.bot_data.get('checklist_data')
    if not checklist_data:
        await update.message.reply_text("К сожалению, чек-лист сейчас недоступен.", reply_markup=get_main_keyboard(context))
        return
    context.user_data['quiz_answers'] = {}
    step = 0
    question_data = checklist_data[step]
    keyboard = make_quiz_keyboard(question_data["answers"], step)
    await update.message.reply_text(question_data["question"], reply_markup=keyboard)

async def checklist_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    client_id, manager_contact = get_client_context(context)
    checklist_data = context.bot_data.get('checklist_data')
    if not checklist_data:
        await query.edit_message_text(text="Произошла ошибка: структура чек-листа не найдена.")
        return
    lead_service: LeadService = context.application.bot_data['lead_service']
    parts = query.data.split('_')
    step = int(parts[2])
    answer_index = int(parts[4])
    question_data = checklist_data[step]
    answer_data = question_data["answers"][answer_index]
    question_text = re.sub(r'^\d+/\d+\.\s*', '', question_data["question"])
    context.user_data.setdefault('quiz_answers', {})[question_text] = answer_data["text"]
    next_step = step + 1
    if next_step < len(checklist_data):
        next_question_data = checklist_data[next_step]
        keyboard = make_quiz_keyboard(next_question_data["answers"], next_step)
        await query.edit_message_text(text=next_question_data["question"], reply_markup=keyboard)
    else:
        user = query.from_user
        quiz_answers = context.user_data.get('quiz_answers', {})
        lead_service.repo.save_quiz_results(user.id, quiz_answers, client_id)
        lead_service.bot = context.bot
        await lead_service.send_quiz_results_to_manager(user, quiz_answers, manager_contact)
        await query.edit_message_text(text="Спасибо за ваши ответы! Мы скоро свяжемся с вами для подробной консультации.")
        context.user_data.pop('quiz_answers', None)

async def start_checklist_from_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    checklist_data = context.bot_data.get('checklist_data')
    if not checklist_data:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("К сожалению, чек-лист сейчас недоступен.")
        return
    await query.edit_message_reply_markup(reply_markup=None)
    context.user_data['quiz_answers'] = {}
    step = 0
    question_data = checklist_data[step]
    keyboard = make_quiz_keyboard(question_data["answers"], step)
    await query.message.reply_text(question_data["question"], reply_markup=keyboard)

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
    lead_service: LeadService = context.application.bot_data['lead_service']
    client_id, manager_contact = get_client_context(context)
    user_data = update.effective_user
    context.user_data['region'] = update.message.text
    user = User(id=user_data.id, username=user_data.username, first_name=user_data.first_name)
    lead_service.bot = context.bot
    await lead_service.save_lead(user, context.user_data, client_id, manager_contact)
    await update.message.reply_text("Спасибо за ваши ответы! Наши специалисты скоро свяжутся с вами.", reply_markup=get_main_keyboard(context))
    lead_magnet_enabled = context.bot_data.get('lead_magnet_enabled')
    lead_magnet_file_id = context.bot_data.get('lead_magnet_file_id')
    if lead_magnet_enabled and lead_magnet_file_id:
        logger.info(f"Client {client_id} has lead magnet enabled. Sending file...")
        try:
            await update.message.reply_text("🎁 В качестве благодарности, отправляю вам полезный материал...")
            await update.message.reply_chat_action(ChatAction.UPLOAD_DOCUMENT)
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=lead_magnet_file_id,
                caption="Здесь ваш бонусный материал!"
            )
        except TelegramError as e:
            logger.error(
                f"Failed to send lead magnet file {lead_magnet_file_id} "
                f"for client {client_id} to user {user.id}. Error: {e}",
                exc_info=True
            )
            await update.message.reply_text("К сожалению, не удалось отправить бонусный файл. Мы решим эту проблему и вышлем его вам позже.")
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Заполнение анкеты отменено.", reply_markup=get_main_keyboard(context))
    context.user_data.clear()
    return ConversationHandler.END
# path: src/api/telegram/user_handlers.py