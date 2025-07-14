import os
import google.generativeai as genai
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# 1. КОНФИГУРАЦИЯ
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)
MODEL_NAME = "gemini-1.5-flash-latest"

# Читаем базу знаний
try:
    with open('bankruptcy_law.md', 'r', encoding='utf-8') as f:
        BANKRUPTCY_CONTEXT = f.read()
    with open('interviews.md', 'r', encoding='utf-8') as f:
        INTERVIEWS_CONTEXT = f.read()
    KNOWLEDGE_BASE = BANKRUPTCY_CONTEXT + "\n\n" + INTERVIEWS_CONTEXT
    print("База знаний успешно загружена.")
except FileNotFoundError:
    KNOWLEDGE_BASE = ""
    print("Внимание: Файлы с базой знаний не найдены.")


# 2. ФУНКЦИИ-ОБРАБОТЧИКИ
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Здравствуйте! Я ваш юридический AI-ассистент. Задайте мне вопрос.')

def get_ai_response(question: str) -> str:
    """Отправляет вопрос и базу знаний напрямую в Google AI и возвращает ответ."""

    # ИЗМЕНЕНИЕ: НОВАЯ ЗАДАЧА ДЛЯ БОТА - КРАТКОСТЬ!
    system_prompt = (
        "Твоя роль — первоклассный юридический помощник. Твое имя — Вячеслав. "
        "Твоя речь — человечная, мягкая и эмпатичная. "
        "Твоя задача — **кратко и в общих чертах разъяснять сложные юридические вопросы**, донося только самую важную суть."
        "**СТРОГИЕ ПРАВИЛА:**"
        "1. **Краткость:** Твой ответ должен быть сжатым, в идеале 2-3 абзаца. Не углубляйся в детали без необходимости."
        "2. **Никогда не представляйся**, если тебя не спросили напрямую 'Как тебя зовут?'. Сразу переходи к сути ответа."
        "3. **Никогда не упоминай** слова 'контекст' или 'предоставленная информация'. Отвечай так, будто эта информация — твои собственные знания."
        "4. **Для форматирования** используй теги HTML: <b>...</b> для жирного, <i>...</i> для курсива. Для создания абзаца используй ОДНУ пустую строку."
    )

    full_prompt = f"{system_prompt}\n\nВот база знаний для твоего ответа:\n{KNOWLEDGE_BASE}\n\nВопрос клиента: {question}"

    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        print(f"Ошибка при обращении к Google AI: {e}")
        return "К сожалению, произошла ошибка при обращении к AI-сервису. Попробуйте позже."

def handle_message(update: Update, context: CallbackContext) -> None:
    user_question = update.message.text
    update.message.reply_text("Думаю над вашим вопросом...") 

    ai_answer = get_ai_response(user_question)

    # Наша надежная очистка ответа
    cleaned_answer = ai_answer.replace('<p>', '').replace('</p>', '')
    while '\n\n\n' in cleaned_answer:
        cleaned_answer = cleaned_answer.replace('\n\n\n', '\n\n')

    try:
        update.message.reply_text(cleaned_answer, parse_mode='HTML')
    except Exception as e:
        print(f"Ошибка форматирования HTML или другая ошибка отправки: {e}")
        update.message.reply_text(cleaned_answer)


# 3. ОСНОВНАЯ ЧАСТЬ - ЗАПУСК БОТА
def main() -> None:
    updater = Updater(TELEGRAM_TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    print("Бот запущен и работает с прямым доступом к Google AI...")
    updater.idle()


if __name__ == '__main__':
    main()