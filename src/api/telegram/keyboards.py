# START OF FILE: src/api/telegram/keyboards.py

from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict

# ИЗМЕНЕНИЕ: Добавляем новую кнопку "Пройти квиз"
main_keyboard = ReplyKeyboardMarkup(
    [
        ['📝 Заполнить анкету', '🧑‍💼 Связаться с человеком'],
        ['🎯 Пройти квиз на банкротство']
    ],
    resize_keyboard=True
)

cancel_keyboard = ReplyKeyboardMarkup(
    [['Отмена']],
    resize_keyboard=True
)

# НОВАЯ ФУНКЦИЯ: Динамически создает инлайн-клавиатуру для шага квиза
def make_quiz_keyboard(answers: List[Dict], step: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для текущего вопроса квиза."""
    buttons = []
    for i, answer in enumerate(answers):
        # callback_data будет содержать информацию о шаге и индексе ответа
        callback_data = f"quiz_step_{step}_answer_{i}"
        buttons.append([InlineKeyboardButton(answer["text"], callback_data=callback_data)])
    
    return InlineKeyboardMarkup(buttons)

# END OF FILE: src/api/telegram/keyboards.py