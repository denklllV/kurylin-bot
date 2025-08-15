# START OF FILE: src/api/telegram/handlers.py

import io
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode, ChatAction
from pydub import AudioSegment

from src.app.services.ai_service import AIService
from src.app.services.lead_service import LeadService
from src.app.services.analytics_service import AnalyticsService
from src.domain.models import User, Message
from src.api.telegram.keyboards import main_keyboard, cancel_keyboard, make_quiz_keyboard
from src.api.telegram.quiz_data import QUIZ_DATA
from src.shared.logger import logger
from src.shared.config import GET_NAME, GET_DEBT, GET_INCOME, GET_REGION, MANAGER_CHAT_ID

async def _process_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE, user_question: str):
    """
    Основная функция обработки сообщений с классификацией и предложением квиза.
    """
    ai_service: AIService = context.bot_data['ai_service']
    user_id = update.effective_user.id
    
    # --- Классификация первого запроса ---
    user_category = ai_service.repo.get_user_category(user_id)
    if user_category is None:
        logger.info(f"User {user_id} has no category. Classifying their first message...")
        new_category = ai_service.classify_text(user_question)
        if new_category:
            ai_service.repo.update_user_category(user_id, new_category)

    ai_service.repo.save_message(user_id, Message(role='user', content=user_question))
    await update.message.reply_chat_action(ChatAction.TYPING)

    response_text, debug_info = ai_service.get_text_response(user_id, user_question)
    context.bot_data['last_debug_info'] = debug_info
    ai_service.repo.save_message(user_id, Message(role='assistant', content=response_text))
    
    # --- Проактивное предложение квиза ---
    quiz_completed, _ = ai_service.repo.get_user_quiz_status(user_id)
    reply_markup = main_keyboard
    parse_mode = None 
    
    if not quiz_completed:
        quiz_prompt_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 Пройти квиз для точной оценки", callback_data="start_quiz_from_prompt")]
        ])
        reply_markup = quiz_prompt_keyboard
        # Экранируем точки для MarkdownV2
        response_text += "\n\n_Чтобы я мог дать более точную рекомендацию, пройдите короткий квиз\\._"
        parse_mode = ParseMode.MARKDOWN_V2

    if isinstance(reply_markup, InlineKeyboardMarkup):
        await update.message.reply_text(response_text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        await update.message.reply_text(response_text, reply_markup=reply_markup, parse_mode=parse_mode)

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
    lead_service.repo.save_user(user)

    await update.message.reply_text(
        'Здравствуйте! Я ваш юридический AI-ассистент.\n\n'
        '📝 Чтобы начать анкету, нажмите кнопку ниже.\n'
        '🎯 Пройдите квиз, чтобы получить точную оценку.\n'
        '❓ Чтобы задать вопрос, просто напишите его в этот чат.',
        reply_markup=main_keyboard
    )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _process_user_message(update, context, update.message.text)

async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ai_service: AIService = context.bot_data['ai_service']
    await update.message.reply_text("Получил ваше голосовое, расшифровываю...")
    await update.message.reply_chat_action(ChatAction.TYPING)

    voice = update.message.voice
    voice_file = await voice.get_file()
    voice_bytes = await voice_file.download_as_bytearray()
    
    try:
        ogg_stream = io.BytesIO(voice_bytes)
        audio = AudioSegment.from_file(ogg_stream)
        mp3_stream = io.BytesIO()
        audio.export(mp3_stream, format="mp3")
        mp3_stream.seek(0)
        transcribed_text = ai_service.transcribe_voice(mp3_stream.read())
    except Exception as e:
        logger.error(f"Error converting audio: {e}", exc_info=True)
        transcribed_text = None

    if transcribed_text:
        await update.message.reply_text(f"Ваш вопрос: «{transcribed_text}»\n\nОбрабатываю...")
        await _process_user_message(update, context, transcribed_text)
    else:
        await update.message.reply_text("К сожалению, не удалось распознать речь. Попробуйте записать снова или напишите вопрос текстом.")

async def contact_human(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = f"@{user.username}" if user.username else f"ID: {user.id}"
    message_for_manager = f"<b>🧑‍💼 Запрос на связь от {username}</b>\n\nПожалуйста, свяжитесь с этим пользователем."
    if MANAGER_CHAT_ID:
        await context.bot.send_message(chat_id=MANAGER_CHAT_ID, text=message_for_manager, parse_mode=ParseMode.HTML)
    await update.message.reply_text("Ваш запрос отправлен менеджеру.", reply_markup=main_keyboard)

# --- QUIZ HANDLERS ---
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает квиз, отправляя первый вопрос."""
    context.user_data['quiz_answers'] = {}
    step = 0
    question_data = QUIZ_DATA[step]
    
    keyboard = make_quiz_keyboard(question_data["answers"], step)
    await update.message.reply_text(question_data["question"], reply_markup=keyboard)

async def quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ответ на вопрос квиза и отправляет следующий, либо завершает квиз."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split('_')
    step = int(parts[2])
    answer_index = int(parts[4])

    question_data = QUIZ_DATA[step]
    answer_data = question_data["answers"][answer_index]
    
    question_text = re.sub(r'^\d+/\d+\.\s*', '', question_data["question"])
    context.user_data.setdefault('quiz_answers', {})[question_text] = answer_data["text"]

    next_step = step + 1
    if next_step < len(QUIZ_DATA):
        next_question_data = QUIZ_DATA[next_step]
        keyboard = make_quiz_keyboard(next_question_data["answers"], next_step)
        await query.edit_message_text(text=next_question_data["question"], reply_markup=keyboard)
    else:
        lead_service: LeadService = context.bot_data['lead_service']
        user = update.effective_user
        quiz_answers = context.user_data.get('quiz_answers', {})
        
        lead_service.repo.save_quiz_results(user.id, quiz_answers)
        await lead_service.send_quiz_results_to_manager(user, quiz_answers)

        await query.edit_message_text(text="Спасибо за ваши ответы! Мы скоро свяжемся с вами для подробной консультации.")
        context.user_data.pop('quiz_answers', None)

async def start_quiz_from_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускает квиз по нажатию инлайн-кнопки."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_reply_markup(reply_markup=None)

    context.user_data['quiz_answers'] = {}
    step = 0
    question_data = QUIZ_DATA[step]
    keyboard = make_quiz_keyboard(question_data["answers"], step)
    await query.message.reply_text(question_data["question"], reply_markup=keyboard)
        
# --- ADMIN DEBUG HANDLERS ---
def is_admin(update: Update) -> bool:
    return str(update.effective_user.id) == MANAGER_CHAT_ID

async def last_answer_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    debug_info = context.bot_data.get('last_debug_info')
    if not debug_info:
        await update.message.reply_text("Отладочная информация еще не была записана.")
        return
    rag_chunks = debug_info.get('rag_chunks', [])
    rag_report = "\n\n".join(f"<b>Score: {chunk.get('similarity', 0):.4f}</b>\n<i>{chunk.get('content', '')}</i>" for chunk in rag_chunks) if rag_chunks else "<i>Ничего не найдено в базе знаний.</i>"
    history = debug_info.get('conversation_history', [])
    history_report = "\n".join(f"<b>{msg['role']}:</b> {msg['content']}" for msg in history) if history else "<i>История диалога пуста.</i>"
    report = (f"<b>--- Отладка последнего ответа ---</b>\n\n" f"<b>Время обработки:</b> {debug_info.get('processing_time', 'N/A')}\n" f"<b>Вопрос пользователя:</b> {debug_info.get('user_question', 'N/A')}\n\n" f"<b>--- Использованная история диалога ---</b>\n{history_report}\n\n" f"<b>--- Найденный контекст (RAG) ---</b>\n{rag_report}")
    await update.message.reply_text(report, parse_mode=ParseMode.HTML)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    await update.message.reply_text("Собираю статистику, это может занять несколько секунд...")
    analytics_service: AnalyticsService = context.bot_data['analytics_service']
    report = analytics_service.generate_summary_report()
    await update.message.reply_text(report, parse_mode=ParseMode.HTML)

async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    report = f"✅ Бот в сети.\n" f"🔑 Менеджер ({MANAGER_CHAT_ID}) определен."
    await update.message.reply_text(report)

# --- FORM LOGIC ---
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
    lead_service: LeadService = context.bot_data['lead_service']
    user_data = update.effective_user
    context.user_data['region'] = update.message.text
    user = User(id=user_data.id, username=user_data.username, first_name=user_data.first_name)
    await lead_service.save_lead(user, context.user_data)
    await update.message.reply_text("Спасибо за ваши ответы! Наши специалисты скоро свяжутся с вами.", reply_markup=main_keyboard)
    context.user_data.clear()
    return ConversationHandler.END
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Заполнение анкеты отменено.", reply_markup=main_keyboard)
    context.user_data.clear()
    return ConversationHandler.END

# END OF FILE: src/api/telegram/handlers.py