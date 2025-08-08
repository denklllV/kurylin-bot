# START OF FILE: src/api/telegram/handlers.py

import os
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode, ChatAction
from pydub import AudioSegment

from src.app.services.ai_service import AIService
from src.app.services.lead_service import LeadService
from src.infra.clients.supabase_repo import SupabaseRepo
from src.domain.models import User, Message
from src.api.telegram.keyboards import main_keyboard, cancel_keyboard
from src.shared.logger import logger
from src.shared.config import GET_NAME, GET_DEBT, GET_INCOME, GET_REGION, MANAGER_CHAT_ID

# --- Инициализация сервисов (в реальном приложении это будет делаться в main.py через DI) ---
# Для простоты рефакторинга пока создаем их здесь.
supabase_repo = SupabaseRepo()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = update.effective_user
    utm_source = context.args[0] if context.args else None
    
    user = User(
        id=user_data.id,
        username=user_data.username,
        first_name=user_data.first_name,
        utm_source=utm_source
    )
    supabase_repo.save_user(user)

    await update.message.reply_text(
        'Здравствуйте! Я ваш юридический AI-ассистент.\n\n'
        '📝 Чтобы начать анкетирование, нажмите кнопку ниже.\n'
        '❓ Чтобы задать вопрос, просто напишите его в этот чат.',
        reply_markup=main_keyboard
    )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ai_service: AIService = context.bot_data['ai_service']
    user_id = update.effective_user.id
    user_question = update.message.text
    
    supabase_repo.save_message(user_id, Message(role='user', content=user_question))
    await update.message.reply_chat_action(ChatAction.TYPING)

    response_text = ai_service.get_text_response(user_question)
    
    supabase_repo.save_message(user_id, Message(role='assistant', content=response_text))
    await update.message.reply_text(response_text, parse_mode=ParseMode.HTML, reply_markup=main_keyboard)

async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ai_service: AIService = context.bot_data['ai_service']
    user_id = update.effective_user.id

    await update.message.reply_text("Получил ваше голосовое, расшифровываю...")
    await update.message.reply_chat_action(ChatAction.TYPING)

    voice = update.message.voice
    voice_file = await voice.get_file()
    
    # Конвертация в MP3 в памяти
    ogg_audio = AudioSegment.from_file(await voice_file.download_as_bytearray())
    mp3_data = ogg_audio.export(format="mp3").read()

    transcribed_text = ai_service.transcribe_voice(mp3_data)

    if transcribed_text:
        await update.message.reply_text(f"Ваш вопрос: «{transcribed_text}»\n\nИщу ответ...")
        
        supabase_repo.save_message(user_id, Message(role='user', content=transcribed_text))
        await update.message.reply_chat_action(ChatAction.TYPING)
        
        response_text = ai_service.get_text_response(transcribed_text)

        supabase_repo.save_message(user_id, Message(role='assistant', content=response_text))
        await update.message.reply_text(response_text, parse_mode=ParseMode.HTML, reply_markup=main_keyboard)
    else:
        await update.message.reply_text("К сожалению, не удалось распознать речь. Попробуйте записать снова или напишите вопрос текстом.")

async def contact_human(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = f"@{user.username}" if user.username else f"ID: {user.id}"
    message_for_manager = f"<b>🧑‍💼 Запрос на связь от {username}</b>\n\nПожалуйста, свяжитесь с этим пользователем."
    
    if MANAGER_CHAT_ID:
        await context.bot.send_message(chat_id=MANAGER_CHAT_ID, text=message_for_manager, parse_mode=ParseMode.HTML)
    
    await update.message.reply_text("Ваш запрос отправлен менеджеру.", reply_markup=main_keyboard)

# --- Логика анкеты ---
async def start_form(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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