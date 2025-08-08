# START OF FILE: src/api/telegram/keyboards.py

from telegram import ReplyKeyboardMarkup

main_keyboard = ReplyKeyboardMarkup(
    [['📝 Заполнить анкету', '🧑‍💼 Связаться с человеком']],
    resize_keyboard=True
)

cancel_keyboard = ReplyKeyboardMarkup(
    [['Отмена']],
    resize_keyboard=True
)

# END OF FILE: src/api/telegram/keyboards.py