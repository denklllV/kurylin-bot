# START OF FILE: src/api/telegram/quiz_data.py

QUIZ_DATA = [
    {
        "question": "1/4. Какой у вас общий размер задолженности?",
        "answers": [
            {"text": "Менее 300 000 ₽", "value": "<300k"},
            {"text": "300 000–500 000 ₽", "value": "300k-500k"},
            {"text": "Более 500 000 ₽", "value": ">500k"},
        ],
    },
    {
        "question": "2/4. Есть ли у вас просрочки по платежам более 3 месяцев?",
        "answers": [
            {"text": "Да, есть", "value": "yes_delay"},
            {"text": "Нет", "value": "no_delay"},
        ],
    },
    {
        "question": "3/4. Проходили ли вы процедуру банкротства в последние 5 лет?",
        "answers": [
            {"text": "Да, проходил(а)", "value": "yes_bankruptcy"},
            {"text": "Нет, не проходил(а)", "value": "no_bankruptcy"},
        ],
    },
    {
        "question": "4/4. Каков ваш официальный доход на данный момент?",
        "answers": [
            {"text": "Стабильный, достаточный для выплат", "value": "stable_income"},
            {"text": "Нестабильный или сильно снизился", "value": "unstable_income"},
            {"text": "Отсутствует", "value": "no_income"},
        ],
    },
]

# END OF FILE: src/api/telegram/quiz_data.py