# START OF FILE: src/api/telegram/keyboards.py

from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict
from telegram.ext import ContextTypes

def get_main_keyboard(context: ContextTypes.DEFAULT_TYPE) -> ReplyKeyboardMarkup:
    base_buttons = [
        ['📝 Заполнить анкету', '🧑‍💼 Связаться с человеком'],
    ]
    quiz_data = context.bot_data.get('quiz_data')
    if quiz_data:
        base_buttons.append(['🎯 Квиз'])
    return ReplyKeyboardMarkup(base_buttons, resize_keyboard=True)

# ИЗМЕНЕНИЕ: Улучшаем текст кнопок
admin_keyboard = ReplyKeyboardMarkup(
    [
        ['📊 Статистика', '📤 Экспорт лидов'],
        ['📜 Управление промптом', '📣 Рассылка'],
        ['🕵️‍♂️ Отладка ответа']
    ],
    resize_keyboard=True
)

cancel_keyboard = ReplyKeyboardMarkup(
    [['Отмена']],
    resize_keyboard=True
)

def make_quiz_keyboard(answers: List[Dict], step: int) -> InlineKeyboardMarkup:
    buttons = []
    for i, answer in enumerate(answers):
        callback_data = f"quiz_step_{step}_answer_{i}"
        buttons.append([InlineKeyboardButton(answer["text"], callback_data=callback_data)])
    return InlineKeyboardMarkup(buttons)

# END OF FILE: src/api/telegram/keyboards.py