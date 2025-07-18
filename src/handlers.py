# src/handlers.py
import asyncio
import os
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from pydub import AudioSegment

# Добавляем импорт новых переменных
from .config import logger, MANAGER_CHAT_ID, RENDER_SERVICE_NAME, GET_NAME, GET_DEBT, GET_INCOME, GET_REGION, LEAD_MAGNET_ENABLED, LEAD_MAGNET_FILE_ID
from .database import save_user_to_db, save_lead_to_db, get_lead_user_ids
from .bot_keyboards import main_keyboard, cancel_keyboard
from .ai_logic import get_ai_response, transcribe_voice

# ... весь код до функции get_region остается без изменений ...
# (send_notification_to_manager, whoami, start, handle_text_message, handle_voice_message, 
# contact_human, handle_admin_document, handle_broadcast_pdf, broadcast_command_handler, 
# handle_broadcast, handle_broadcast_dry_run, start_form, get_name, get_debt, get_income)

# Я привожу полный код файла для соблюдения нашего правила,
# но реальные изменения находятся только в функции get_region.

LAST_PDF_FILE_ID = None

async def send_notification_to_manager(context: ContextTypes.DEFAULT_TYPE, message_text: str):
    if not MANAGER_CHAT_ID:
        logger.warning("Переменная MANAGER_CHAT_ID не установлена.")
        return
    try:
        await context.bot.send_message(chat_id=MANAGER_CHAT_ID, text=message_text, parse_mode=ParseMode.HTML)
        logger.info(f"Уведомление успешно отправлено менеджеру.")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление менеджеру: {e}")

async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    service_name = RENDER_SERVICE_NAME or "Не определено"
    await update.message.reply_text(f"Я запущен на сервисе: {service_name}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    utm_source = context.args[0] if context.args else None
    if utm_source:
        logger.info(f"Пользователь {user.id} пришел с UTM-меткой: {utm_source}")
    save_user_to_db(user_id=user.id, username=user.username, first_name=user.first_name, utm_source=utm_source)
    await update.message.reply_text(
        'Здравствуйте! Я ваш юридический AI-ассистент.\n\n'
        '📝 Чтобы начать анкетирование, нажмите кнопку ниже.\n'
        '❓ Чтобы задать вопрос, просто напишите его в этот чат.',
        reply_markup=main_keyboard
    )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text_override: str = None) -> None:
    user_question = text_override or update.message.text
    if not text_override:
        await update.message.reply_text("Думаю над вашим вопросом...")
    loop = asyncio.get_running_loop()
    ai_answer = await loop.run_in_executor(None, get_ai_response, user_question)
    cleaned_answer = ai_answer.replace('<p>', '').replace('</p>', '')
    while '\n\n\n' in cleaned_answer:
        cleaned_answer = cleaned_answer.replace('\n\n\n', '\n\n')
    try:
        await update.message.reply_text(cleaned_answer, parse_mode=ParseMode.HTML, reply_markup=main_keyboard)
    except Exception as e:
        logger.error(f"Ошибка форматирования HTML: {e}. Отправка без форматирования.")
        await update.message.reply_text(cleaned_answer, reply_markup=main_keyboard)

async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Получил ваше голосовое, расшифровываю...")
    voice = update.message.voice
    voice_file = await voice.get_file()
    os.makedirs('temp', exist_ok=True)
    ogg_path = f"temp/{voice.file_id}.ogg"
    await voice_file.download_to_drive(ogg_path)
    mp3_path = f"temp/{voice.file_id}.mp3"
    transcribed_text = None
    try:
        AudioSegment.from_ogg(ogg_path).export(mp3_path, format="mp3")
        logger.info(f"Файл успешно конвертирован в {mp3_path}")
        loop = asyncio.get_running_loop()
        transcribed_text = await loop.run_in_executor(None, transcribe_voice, mp3_path)
    except Exception as e:
        logger.error(f"Ошибка в процессе обработки голоса: {e}")
    os.remove(ogg_path)
    if os.path.exists(mp3_path):
        os.remove(mp3_path)
    if transcribed_text:
        await update.message.reply_text(f"Ваш вопрос: «{transcribed_text}»\n\nИщу ответ...")
        await handle_text_message(update, context, text_override=transcribed_text)
    else:
        await update.message.reply_text("К сожалению, не удалось распознать речь. Попробуйте записать снова или напишите вопрос текстом.")

async def contact_human(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message_for_manager = f"<b>🧑‍💼 Запрос на связь от @{user.username} (ID: {user.id})</b>\n\nПожалуйста, свяжитесь с этим пользователем."
    await send_notification_to_manager(context, message_for_manager)
    await update.message.reply_text("Ваш запрос отправлен менеджеру.", reply_markup=main_keyboard)

async def handle_admin_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_user.id) != MANAGER_CHAT_ID:
        logger.warning(f"Пользователь {update.effective_user.id} попытался загрузить документ, не будучи админом.")
        return
    if not update.message.document:
        return
    global LAST_PDF_FILE_ID
    LAST_PDF_FILE_ID = update.message.document.file_id
    logger.info(f"Администратор загрузил новый PDF. File ID: {LAST_PDF_FILE_ID}")
    await update.message.reply_text(
        f"✅ Файл '{update.message.document.file_name}' получен и готов к ручной рассылке.\n"
        f"Его File ID: <code>{LAST_PDF_FILE_ID}</code> (можно использовать для авто-лидмагнита).\n\n"
        f"Для ручной отправки используйте <code>/broadcast_pdf Ваш текст...</code>",
        parse_mode=ParseMode.HTML
    )

async def handle_broadcast_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_user.id) != MANAGER_CHAT_ID:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return
    if not LAST_PDF_FILE_ID:
        await update.message.reply_text("Сначала нужно отправить мне PDF-файл, который вы хотите разослать.")
        return
    caption_text = " ".join(context.args)
    if not caption_text:
        await update.message.reply_text("Вы не указали текст подписи для файла. Пример: /broadcast_pdf Это важный документ.")
        return
    user_ids = get_lead_user_ids()
    if not user_ids:
        await update.message.reply_text("Не найдено ни одного пользователя, заполнившего анкету.")
        return
    await update.message.reply_text(f"Начинаю рассылку PDF-файла для {len(user_ids)} пользователей...")
    successful_sends = 0
    failed_sends = 0
    for user_id in user_ids:
        try:
            await context.bot.send_document(
                chat_id=user_id, document=LAST_PDF_FILE_ID, caption=caption_text, parse_mode=ParseMode.HTML
            )
            successful_sends += 1
        except Exception as e:
            failed_sends += 1
            logger.error(f"Ошибка при отправке PDF пользователю {user_id}: {e}")
        await asyncio.sleep(0.1)
    await update.message.reply_text(
        f"✅ Рассылка PDF завершена!\nУспешно отправлено: {successful_sends}\nНе удалось отправить: {failed_sends}"
    )

async def broadcast_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, dry_run: bool):
    if str(update.effective_user.id) != MANAGER_CHAT_ID:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return
    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("Вы не указали сообщение для рассылки. Пример: /broadcast Привет, мир!")
        return
    user_ids = get_lead_user_ids()
    if not user_ids:
        await update.message.reply_text("Не найдено ни одного пользователя, заполнившего анкету.")
        return
    if dry_run:
        await update.message.reply_text(
            f"--- ТЕСТОВЫЙ ЗАПУСК ---\n"
            f"Сообщение было бы отправлено {len(user_ids)} пользователям.\n"
            f"Текст: «{message}»"
        )
        return
    await update.message.reply_text(f"Начинаю рассылку для {len(user_ids)} пользователей...")
    successful_sends = 0
    failed_sends = 0
    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=message, parse_mode=ParseMode.HTML)
            successful_sends += 1
        except Exception as e:
            failed_sends += 1
            logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
        await asyncio.sleep(0.1)
    await update.message.reply_text(
        f"✅ Рассылка завершена!\nУспешно отправлено: {successful_sends}\nНе удалось отправить: {failed_sends}"
    )

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await broadcast_command_handler(update, context, dry_run=False)

async def handle_broadcast_dry_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await broadcast_command_handler(update, context, dry_run=True)

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
    """
    Последний шаг анкеты. Сохраняет данные и опционально отправляет лид-магнит.
    """
    context.user_data['region'] = update.message.text
    user = update.effective_user
    user_info = context.user_data
    save_lead_to_db(user_id=user.id, lead_data=user_info)
    
    # Отправляем уведомление менеджеру
    summary_for_manager = (
        f"<b>✅ Новая анкета от @{user.username} (ID: {user.id})</b>\n\n"
        f"<b>Имя:</b> {user_info.get('name', '-')}\n"
        f"<b>Сумма долга:</b> {user_info.get('debt', '-')}\n"
        f"<b>Источник дохода:</b> {user_info.get('income', '-')}\n"
        f"<b>Регион:</b> {user_info.get('region', '-')}"
    )
    await send_notification_to_manager(context, summary_for_manager)
    
    # Отправляем пользователю сообщение о завершении
    await update.message.reply_text("Спасибо за ваши ответы! Наши специалисты скоро свяжутся с вами.", reply_markup=main_keyboard)
    
    # --- НАЧАЛО НОВОЙ ЛОГИКИ ЛИД-МАГНИТА ---
    if LEAD_MAGNET_ENABLED and LEAD_MAGNET_FILE_ID:
        try:
            logger.info(f"Отправка лид-магнита (File ID: {LEAD_MAGNET_FILE_ID}) пользователю {user.id}")
            await context.bot.send_document(
                chat_id=user.id,
                document=LEAD_MAGNET_FILE_ID,
                caption="В благодарность за уделенное время, примите этот полезный материал."
            )
        except Exception as e:
            logger.error(f"Не удалось отправить автоматический лид-магнит пользователю {user.id}: {e}")
    # --- КОНЕЦ НОВОЙ ЛОГИКИ ---
            
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Заполнение анкеты отменено.", reply_markup=main_keyboard)
    context.user_data.clear()
    return ConversationHandler.END