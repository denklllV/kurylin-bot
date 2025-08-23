# START OF FILE: src/api/telegram/keyboards.py

from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict
from telegram.ext import ContextTypes

def get_main_keyboard(context: ContextTypes.DEFAULT_TYPE) -> ReplyKeyboardMarkup:
    """
    Создает главную клавиатуру, добавляя кнопку "Чек-лист" только если
    конфигурация чек-листа существует для данного клиента.
    """
    base_buttons = [
        ['📝 Заполнить анкету', '🧑‍💼 Связаться с человеком'],
    ]
    
    # ИЗМЕНЕНИЕ: Проверяем checklist_data вместо quiz_data
    checklist_data = context.bot_data.get('checklist_data')
    if checklist_data:
        # ИЗМЕНЕНИЕ: Меняем название кнопки
        base_buttons.append(['🎯 Чек-лист'])
        
    return ReplyKeyboardMarkup(base_buttons, resize_keyboard=True)

admin_keyboard = ReplyKeyboardMarkup(
    [
        ['📊 Статистика', '📤 Экспорт лидов'],
        ['📜 Управление промптом', '📣 Рассылка'],
        # ИЗМЕНЕНИЕ: Меняем название кнопки
        ['🧩 Управление Чек-листом', '🕵️‍♂️ Отладка ответа']
    ],
    resize_keyboard=True
)

cancel_keyboard = ReplyKeyboardMarkup(
    [['Отмена']],
    resize_keyboard=True
)

broadcast_confirm_keyboard = ReplyKeyboardMarkup(
    [
        ['✅ Отправить всем', '📝 Редактировать'],
        ['❌ Отмена']
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)


def make_quiz_keyboard(answers: List[Dict], step: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для текущего вопроса чек-листа/квиза."""
    buttons = []
    for i, answer in enumerate(answers):
        callback_data = f"quiz_step_{step}_answer_{i}"
        buttons.append([InlineKeyboardButton(answer["text"], callback_data=callback_data)])
    
    return InlineKeyboardMarkup(buttons)

# END OF FILE: src/api/telegram/keyboards.py