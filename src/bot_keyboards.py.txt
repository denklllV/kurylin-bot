# src/bot_keyboards.py
from telegram import ReplyKeyboardMarkup

# Главная клавиатура с двумя основными действиями
main_keyboard = ReplyKeyboardMarkup(
    [['📝 Заполнить анкету', '🧑‍💼 Связаться с человеком']],
    resize_keyboard=True
)

# Клавиатура для отмены внутри сценария анкеты
cancel_keyboard = ReplyKeyboardMarkup(
    [['Отмена']],
    resize_keyboard=True
)