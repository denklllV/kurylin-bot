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
        ['📝 Заполнить анкету', '🧑‍💼 Святься с человеком'],
    ]
    
    checklist_data = context.bot_data.get('checklist_data')
    if checklist_data:
        base_buttons.append(['🎯 Чек-лист'])
        
    return ReplyKeyboardMarkup(base_buttons, resize_keyboard=True)

admin_keyboard = ReplyKeyboardMarkup(
    [
        ['📊 Статистика', '📤 Экспорт лидов'],
        ['📜 Управление промптом', '📣 Рассылка'],
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

# НОВАЯ КЛАВИАТУРА: Меню для управления чек-листом
checklist_management_keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("📥 Загрузить новый", callback_data="checklist_upload"),
            InlineKeyboardButton("🗑️ Удалить текущий", callback_data="checklist_delete")
        ],
        [
            InlineKeyboardButton("👀 Посмотреть текущий", callback_data="checklist_view"),
            InlineKeyboardButton("⬅️ Назад в админ-меню", callback_data="checklist_back")
        ]
    ]
)


def make_quiz_keyboard(answers: List[Dict], step: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для текущего вопроса чек-листа/квиза."""
    buttons = []
    for i, answer in enumerate(answers):
        callback_data = f"quiz_step_{step}_answer_{i}"
        buttons.append([InlineKeyboardButton(answer["text"], callback_data=callback_data)])
    
    return InlineKeyboardMarkup(buttons)

# END OF FILE: src/api/telegram/keyboards.py