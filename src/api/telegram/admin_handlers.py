# path: src/api/telegram/admin_handlers.py
import json
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode, ChatAction

from src.app.services.ai_service import AIService
from src.app.services.lead_service import LeadService
from src.app.services.analytics_service import AnalyticsService
from src.api.telegram.keyboards import (
    admin_keyboard, cancel_keyboard, 
    broadcast_confirm_keyboard, checklist_management_keyboard
)
from src.infra.clients.sheets_client import GoogleSheetsClient
from src.shared.logger import logger
from src.shared.config import (
    GET_BROADCAST_MESSAGE, GET_BROADCAST_MEDIA, CONFIRM_BROADCAST,
    CHECKLIST_ACTION, CHECKLIST_UPLOAD_FILE
)

# --- Вспомогательные функции, общие для всех обработчиков ---
def get_client_context(context: ContextTypes.DEFAULT_TYPE) -> (int, str):
    """Извлекает client_id и manager_contact из контекста бота."""
    client_id = context.bot_data.get('client_id')
    manager_contact = context.bot_data.get('manager_contact')
    return client_id, manager_contact

def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет, является ли пользователь администратором."""
    _, manager_contact = get_client_context(context)
    return str(update.effective_user.id) == manager_contact

# --- Основные команды админ-панели ---

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context): return
    context.user_data['is_admin_mode'] = True
    await update.message.reply_text(
        "Добро пожаловать в панель администратора!\n\nДля выхода и возврата в обычный режим диалога отправьте /start.",
        reply_markup=admin_keyboard
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context): return
    client_id, _ = get_client_context(context)
    analytics_service: AnalyticsService = context.application.bot_data['analytics_service']
    await update.message.reply_chat_action(ChatAction.TYPING)
    report = analytics_service.generate_summary_report(client_id)
    await update.message.reply_text(report, parse_mode=ParseMode.HTML)

async def export_leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context): return
    await update.message.reply_text("Начинаю экспорт. Это может занять до минуты...")
    client_id, _ = get_client_context(context)
    sheet_id = context.bot_data.get('google_sheet_id')
    if not sheet_id:
        await update.message.reply_text("❌ **Ошибка:** ID Google Таблицы не настроен для этого клиента в базе данных.")
        return
    lead_service: LeadService = context.application.bot_data['lead_service']
    start_date_str, end_date_str = None, None
    if context.args and len(context.args) == 2:
        start_date_str, end_date_str = context.args[0], context.args[1]
    try:
        if start_date_str is None:
            today = datetime.today().date()
            start_of_this_week = today - timedelta(days=today.weekday())
            start_date = start_of_this_week - timedelta(days=7)
            end_date = start_date + timedelta(days=6)
            start_date_str, end_date_str = start_date.isoformat(), end_date.isoformat()
        leads_data = lead_service.repo.get_leads_for_export(client_id, start_date_str, end_date_str)
        sheets_client = GoogleSheetsClient(sheet_id=sheet_id)
        result = sheets_client.export_leads(leads_data, start_date_str, end_date_str)
        await update.message.reply_text(f"✅ {result}")
    except Exception as e:
        logger.error(f"Failed to export leads for client {client_id}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Произошла ошибка при экспорте: {e}")

async def last_answer_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context): return
    client_id, _ = get_client_context(context)
    debug_info = context.application.bot_data.get('last_debug_info', {}).get(client_id)
    if not debug_info:
        await update.message.reply_text("Отладочная информация еще не была записана.")
        return
    history = debug_info.get('conversation_history', [])
    history_report = "\n".join(f"<b>{msg['role']}:</b> {msg['content']}" for msg in history) if history else "<i>История диалога пуста.</i>"
    report = (f"<b>--- Отладка последнего ответа (Клиент ID: {client_id}) ---</b>\n\n"
              f"<b>Вопрос пользователя:</b> {debug_info.get('user_question', 'N/A')}\n\n"
              f"<b>--- Использованная история диалога ---</b>\n{history_report}")
    await update.message.reply_text(report, parse_mode=ParseMode.HTML)

# НОВАЯ КОМАНДА: Утилита для получения file_id
async def get_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возвращает file_id для любого отправленного документа, фото, видео или аудио."""
    if not is_admin(update, context): return
    
    # Сначала проверяем, было ли сообщение ответом на другое сообщение
    target_message = update.message.reply_to_message or update.message
    
    file_id = None
    file_type = None

    if target_message.document:
        file_id = target_message.document.file_id
        file_type = "документа"
    elif target_message.photo:
        file_id = target_message.photo[-1].file_id # Берем самое большое разрешение
        file_type = "фото"
    elif target_message.video:
        file_id = target_message.video.file_id
        file_type = "видео"
    elif target_message.audio:
        file_id = target_message.audio.file_id
        file_type = "аудио"
    
    if file_id and file_type:
        response_text = (
            f"<b>ID этого {file_type}:</b>\n\n"
            f"<code>{file_id}</code>\n\n"
            "Используйте этот ID в поле `lead_magnet_file_id` в вашей базе данных."
        )
        await target_message.reply_text(response_text, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(
            "<b>Как использовать:</b>\n\n"
            "1. Отправьте в этот чат нужный файл (PDF, картинку и т.д.).\n"
            "2. Ответьте на сообщение с этим файлом командой /get_file_id.",
            parse_mode=ParseMode.HTML
        )

async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context): return
    client_id, _ = get_client_context(context)
    await update.message.reply_text(f"✅ Бот в сети. ID клиента: {client_id}.")

async def get_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context): return
    client_id, _ = get_client_context(context)
    ai_service: AIService = context.application.bot_data['ai_service']
    current_prompt = ai_service.repo.get_client_system_prompt(client_id)
    if current_prompt:
        response_text = f"<b>Текущий системный промпт (Клиент ID: {client_id}):</b>\n\n<pre>{current_prompt}</pre>"
        await update.message.reply_text(response_text, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("Не удалось получить системный промпт.")

async def set_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context): return
    client_id, _ = get_client_context(context)
    ai_service: AIService = context.application.bot_data['ai_service']
    if not context.args:
        await update.message.reply_text("<b>Ошибка:</b> вы не указали текст промпта.\n\n<b>Пример:</b> /set_prompt Ты — пират.", parse_mode=ParseMode.HTML)
        return
    new_prompt = " ".join(context.args)
    success = ai_service.repo.update_client_system_prompt(client_id, new_prompt)
    if success:
        await update.message.reply_text("✅ Системный промпт успешно обновлен!")
        await get_prompt(update, context)
    else:
        await update.message.reply_text("❌ Произошла ошибка при обновлении промпта.")

async def prompt_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context): return
    await update.message.reply_text(
        "<b>Управление системным промптом:</b>\n\n"
        "Для просмотра: /get_prompt\n"
        "Для установки: /set_prompt [Новый текст]",
        parse_mode=ParseMode.HTML
    )

# --- Мастер управления Чек-листом ---

async def checklist_management_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update, context): return ConversationHandler.END
    await update.message.reply_text(
        "Меню управления Чек-листом. Выберите действие:",
        reply_markup=checklist_management_keyboard
    )
    return CHECKLIST_ACTION

async def checklist_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    client_id, _ = get_client_context(context)
    checklist_data = context.bot_data.get('checklist_data')
    if checklist_data:
        try:
            pretty_json = json.dumps(checklist_data, indent=2, ensure_ascii=False)
            response_text = f"<b>Текущий чек-лист (Клиент ID: {client_id}):</b>\n\n<pre>{pretty_json}</pre>"
            await query.message.reply_text(text=response_text, parse_mode=ParseMode.HTML)
        except TypeError:
            await query.message.reply_text("Ошибка: не удалось отформатировать данные чек-листа.")
    else:
        await query.message.reply_text("ℹ️ Чек-лист для вашего клиента еще не загружен.")
    return CHECKLIST_ACTION

async def checklist_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    client_id, _ = get_client_context(context)
    # Используем любой сервис, чтобы получить доступ к репозиторию
    lead_service: LeadService = context.application.bot_data['lead_service']
    success = lead_service.repo.update_client_checklist(client_id, None)
    if success:
        # Важно: обновляем состояние в памяти, чтобы клавиатура пользователя сразу изменилась
        context.bot_data['checklist_data'] = None
        await query.edit_message_text("✅ Чек-лист успешно удален.")
    else:
        await query.edit_message_text("❌ Произошла ошибка при удалении чек-листа в базе данных.")
    return ConversationHandler.END

async def checklist_upload_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Пожалуйста, отправьте мне файл в формате `.json` с новой структурой чек-листа.\n\n"
        "Для отмены используйте команду /cancel или нажмите кнопку 'Отмена' на клавиатуре.",
        reply_markup=None
    )
    await query.message.reply_text("Ожидаю файл...", reply_markup=cancel_keyboard)
    return CHECKLIST_UPLOAD_FILE

def _validate_checklist_structure(data: any) -> None:
    """Проводит глубокую валидацию структуры чек-листа. Вызывает ValueError при ошибке."""
    if not isinstance(data, list):
        raise ValueError("Структура должна быть списком (JSON array `[...]`).")
    if not data:
        raise ValueError("Список вопросов не может быть пустым.")
    for i, item in enumerate(data, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Элемент #{i} не является объектом (JSON object `{{...}}`).")
        if 'question' not in item or not isinstance(item['question'], str) or not item['question']:
            raise ValueError(f"У элемента #{i} отсутствует или пуст ключ 'question'.")
        if 'answers' not in item or not isinstance(item['answers'], list) or not item['answers']:
            raise ValueError(f"У элемента #{i} отсутствует или пуст ключ 'answers'.")
        for j, answer in enumerate(item['answers'], 1):
            if not isinstance(answer, dict):
                raise ValueError(f"В вопросе #{i}, ответ #{j} не является объектом.")
            if 'text' not in answer or not isinstance(answer['text'], str) or not answer['text']:
                raise ValueError(f"В вопросе #{i}, у ответа #{j} отсутствует или пуст ключ 'text'.")

async def checklist_receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    client_id, _ = get_client_context(context)
    if not update.message.document:
        await update.message.reply_text("Пожалуйста, отправьте именно файл, а не текст.")
        return CHECKLIST_UPLOAD_FILE
    
    doc = update.message.document
    if not doc.file_name.lower().endswith('.json'):
        await update.message.reply_text("❌ **Ошибка:** Файл должен иметь расширение `.json`. Попробуйте снова.")
        return CHECKLIST_UPLOAD_FILE

    file = await doc.get_file()
    file_content_bytes = await file.download_as_bytearray()
    
    try:
        file_content_str = file_content_bytes.decode('utf-8')
        new_checklist_data = json.loads(file_content_str)
        
        # Запускаем нашу новую функцию валидации
        _validate_checklist_structure(new_checklist_data)
        
        lead_service: LeadService = context.application.bot_data['lead_service']
        success = lead_service.repo.update_client_checklist(client_id, new_checklist_data)
        
        if success:
            # Важно: обновляем состояние в памяти
            context.bot_data['checklist_data'] = new_checklist_data
            await update.message.reply_text("✅ Новый чек-лист успешно загружен и сохранен!", reply_markup=admin_keyboard)
            return ConversationHandler.END
        else:
            await update.message.reply_text("❌ Произошла ошибка при сохранении чек-листа в базу данных.", reply_markup=admin_keyboard)
            return ConversationHandler.END
            
    except json.JSONDecodeError:
        await update.message.reply_text("❌ **Ошибка синтаксиса JSON:**\nНе удалось прочитать файл. Проверьте его на валидность (например, через онлайн-валидатор JSON) и попробуйте снова.")
        return CHECKLIST_UPLOAD_FILE
    except ValueError as e:
        await update.message.reply_text(f"❌ **Ошибка структуры данных:**\n{e}\n\nПожалуйста, исправьте файл и отправьте его снова.")
        return CHECKLIST_UPLOAD_FILE
    except Exception as e:
        logger.error(f"Error processing checklist file for client {client_id}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Произошла непредвиденная ошибка: {e}", reply_markup=admin_keyboard)
        return ConversationHandler.END

async def checklist_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    return ConversationHandler.END

async def checklist_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Управление чек-листом отменено.", reply_markup=admin_keyboard)
    return ConversationHandler.END

# --- Мастер Рассылок (ConversationHandler) ---
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update, context): return ConversationHandler.END
    await update.message.reply_text(
        "<b>Шаг 1/3:</b> Отправьте текст сообщения для рассылки.",
        parse_mode=ParseMode.HTML, reply_markup=cancel_keyboard
    )
    return GET_BROADCAST_MESSAGE

async def broadcast_get_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['broadcast_message'] = update.message.text_html
    await update.message.reply_text(
        "<b>Шаг 2/3:</b> Теперь отправьте картинку или документ.\n\n"
        "Или пропустите этот шаг командой /skip",
        parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove()
    )
    return GET_BROADCAST_MEDIA

async def broadcast_get_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message
    media_type, file_id = None, None
    if message.photo:
        media_type, file_id = 'photo', message.photo[-1].file_id
    elif message.document:
        media_type, file_id = 'document', message.document.file_id
    context.user_data['broadcast_media_type'] = media_type
    context.user_data['broadcast_media_file_id'] = file_id
    await update.message.reply_text("Медиафайл получен.")
    await broadcast_preview(update, context)
    return CONFIRM_BROADCAST

async def broadcast_skip_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Шаг с медиа пропущен.")
    await broadcast_preview(update, context)
    return CONFIRM_BROADCAST

async def broadcast_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = context.user_data.get('broadcast_message')
    media_type = context.user_data.get('broadcast_media_type')
    file_id = context.user_data.get('broadcast_media_file_id')
    await update.effective_message.reply_text("<b>Шаг 3/3: Предпросмотр.</b>", parse_mode=ParseMode.HTML)
    try:
        if media_type == 'photo':
            await update.effective_message.reply_photo(photo=file_id, caption=message_text, parse_mode=ParseMode.HTML)
        elif media_type == 'document':
            await update.effective_message.reply_document(document=file_id, caption=message_text, parse_mode=ParseMode.HTML)
        else:
            await update.effective_message.reply_text(message_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.effective_message.reply_text(f"❌ Ошибка предпросмотра: {e}")
    await update.effective_message.reply_text("Выберите действие:", reply_markup=broadcast_confirm_keyboard)

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    client_id, _ = get_client_context(context)
    lead_service: LeadService = context.application.bot_data['lead_service']
    job_context = {
        'bot': context.bot, 'client_id': client_id, 'admin_chat_id': update.effective_chat.id,
        'message': context.user_data.get('broadcast_message'),
        'media_type': context.user_data.get('broadcast_media_type'),
        'media_file_id': context.user_data.get('broadcast_media_file_id')
    }
    context.job_queue.run_once(lead_service._broadcast_message_task, when=1, data=job_context, name=f"broadcast_{client_id}_{update.update_id}")
    await update.message.reply_text(f"✅ Рассылка запущена.", reply_markup=admin_keyboard)
    context.user_data.clear()
    return ConversationHandler.END

async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Создание рассылки отменено.", reply_markup=admin_keyboard)
    context.user_data.clear()
    return ConversationHandler.END
# path: src/api/telegram/admin_handlers.py