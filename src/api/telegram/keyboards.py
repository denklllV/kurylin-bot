# START OF FILE: src/api/telegram/keyboards.py

from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict
from telegram.ext import ContextTypes

# НОВАЯ ФУНКЦИЯ: Динамически создает главную клавиатуру
def get_main_keyboard(context: ContextTypes.DEFAULT_TYPE) -> ReplyKeyboardMarkup:
    """
    Создает главную клавиатуру, добавляя кнопку "Квиз" только если
    конфигурация квиза существует для данного клиента.
    """
    base_buttons = [
        ['📝 Заполнить анкету', '🧑‍💼 Связаться с человеком'],
    ]
    
    # Проверяем, есть ли данные квиза в контексте этого бота
    quiz_data = context.bot_data.get('quiz_data')
    if quiz_data:
        # Если есть, добавляем кнопку квиза в новый ряд
        base_buttons.append(['🎯 Квиз'])
        
    return ReplyKeyboardMarkup(base_buttons, resize_keyboard=True)

cancel_keyboard = ReplyKeyboardMarkup(
    [['Отмена']],
    resize_keyboard=True
)

def make_quiz_keyboard(answers: List[Dict], step: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для текущего вопроса квиза."""
    buttons = []
    for i, answer in enumerate(answers):
        callback_data = f"quiz_step_{step}_answer_{i}"
        buttons.append([InlineKeyboardButton(answer["text"], callback_data=callback_data)])
    
    return InlineKeyboardMarkup(buttons)

# END OF FILE: src/api/telegram/keyboards.py