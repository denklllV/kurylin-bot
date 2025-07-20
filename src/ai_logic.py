# src/ai_logic.py
import json
import requests
from openai import OpenAI
from .config import OPENROUTER_API_KEY, MODEL_NAME, HUGGINGFACE_API_KEY, STT_API_URL, logger

# --- Клиенты API ---
client_openrouter = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

# --- Загрузка структурированной базы знаний ---
def load_json_db(file_path: str):
    """Надежно загружает JSON-файл, обрабатывая возможные ошибки."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning(f"Файл базы знаний {file_path} не найден или содержит ошибку. Связанный функционал будет отключен.")
        return []

FAQ_DB = load_json_db('data/faq.json')
INTERVIEWS_DB = load_json_db('data/interviews.json')

# --- Логика поиска в базе знаний (Старая, легковесная версия) ---

def find_faq_answer(question: str) -> str | None:
    """Ищет точный ответ в базе FAQ по ключевым словам."""
    if not FAQ_DB: return None
    
    question_words = set(question.lower().split())
    best_match_score = 0
    best_answer = None

    for item in FAQ_DB:
        keywords = set(item.get('keywords', []))
        # Используем более точный скоринг: отношение найденных слов к общему числу ключевых слов
        score = len(question_words.intersection(keywords)) / len(keywords) if keywords else 0
        if score > best_match_score:
            best_match_score = score
            best_answer = item.get('answer')

    # Считаем совпадение успешным, если найдено более 40% ключевых слов
    if best_match_score > 0.4:
        logger.info(f"Найден быстрый ответ в FAQ (score: {best_match_score:.2f}). Экономим токены.")
        return best_answer
    
    return None

def find_relevant_quote(question: str) -> dict | None:
    """Ищет наиболее подходящую цитату из интервью по ключевым словам."""
    if not INTERVIEWS_DB: return None
    
    question_words = set(question.lower().split())
    best_match_score = 0
    best_quote_item = None

    for item in INTERVIEWS_DB:
        keywords = set(item.get('keywords', []))
        score = len(question_words.intersection(keywords))
        if score > best_match_score:
            best_match_score = score
            best_quote_item = item
            
    # Возвращаем цитату, даже если найдено всего 2 ключевых слова
    if best_match_score >= 2:
        logger.info(f"Найдена релевантная цитата для контекста (score: {best_match_score}).")
        return best_quote_item
        
    return None

# --- НОВЫЙ ГИБРИДНЫЙ КОНВЕЙЕР ОТВЕТА ---

def get_ai_response(question: str) -> str:
    """
    Основная функция, реализующая гибридную логику ответа.
    """
    # Шаг 1: Попробовать найти прямой ответ в FAQ для экономии.
    faq_answer = find_faq_answer(question)
    if faq_answer:
        return faq_answer

    # Шаг 2: Если в FAQ нет, найти релевантную цитату из интервью.
    # Она будет служить и контекстом, и примером стиля.
    quote_item = find_relevant_quote(question)
    
    # Шаг 3: Готовим контекст и системный промпт для AI.
    context = ""
    if quote_item:
        context = f"Контекст для ответа (используй эти факты и стиль): «{quote_item.get('quote', '')}»"
    else:
        # Если даже цитата не найдена, идем к LLM с пустым контекстом
        logger.info("Ничего не найдено в локальной базе знаний. Обращаюсь к LLM напрямую.")
        context = "Контекста не найдено."

    system_prompt = (
        "Твоя роль — первоклассный юрист-консультант по банкротству, твое имя — Вячеслав Курилин. "
        "Твоя речь — человечная, мягкая, эмпатичная и уверенная, как в предоставленном контексте. Твоя задача — ответить на вопрос клиента."
        
        "**СТРОГИЕ ПРАВИЛА ТВОЕГО ПОВЕДЕНИЯ:**\n"
        "1. **Если предоставлен контекст:** Твой ответ должен быть основан на фактах из этого контекста. Перескажи их суть своими словами, сохраняя экспертный, но человечный стиль, как в примере.\n"
        "2. **Если контекста нет ('Контекста не найдено'):** Дай общий, полезный ответ по теме банкротства, основываясь на своих общих знаниях. Будь краток.\n"
        "3. **Если вопрос не по теме банкротства/долгов:** Вежливо сообщи, что специализируешься только на этих вопросах.\n"
        "4. **Никогда не упоминай** слова 'контекст', 'база знаний' или 'цитата'.\n"
        "5. **Никогда не представляйся**, если не спросили напрямую. Сразу переходи к сути.\n"
        "6. **Используй HTML-теги** для форматирования: <b>...</b> для жирного, <i>...</i> для курсива."
    )
    
    user_prompt = f"{context}\n\nВопрос клиента: {question}"

    try:
        completion = client_openrouter.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=600, # Немного увеличим для более полных ответов
            temperature=0.7 # Вернем температуру для более "живой" речи
        )
        ai_answer = completion.choices[0].message.content
        
        # Если мы использовали цитату, добавляем к ответу красивую ссылку на источник
        if quote_item:
            source_name = quote_item.get('source_name')
            source_url = quote_item.get('source_url')
            if source_name and source_url:
                citation = f'\n\n<i>Источник: <a href="{source_url}">{source_name}</a></i>'
                ai_answer += citation

        return ai_answer
        
    except Exception as e:
        logger.error(f"Ошибка при обращении к OpenRouter AI: {e}")
        return "К сожалению, произошла техническая ошибка при обработке вашего вопроса. Пожалуйста, попробуйте позже."


def transcribe_voice(voice_path: str) -> str | None:
    """Отправляет аудиофайл в HuggingFace Inference API для транскрибации."""
    logger.info(f"Отправка файла {voice_path} в HuggingFace API...")
    try:
        headers = {
            "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
            "Content-Type": "audio/mpeg"
        }
        with open(voice_path, "rb") as f:
            data = f.read()
        response = requests.post(STT_API_URL, headers=headers, data=data)
        response.raise_for_status()
        result = response.json()
        if 'error' in result:
            logger.error(f"Ошибка от HuggingFace API: {result['error']}")
            return None
        transcribed_text = result.get('text')
        logger.info(f"Аудио успешно транскрибировано через HuggingFace: «{transcribed_text}»")
        return transcribed_text
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка HTTP-запроса при транскрибации: {e}")
        if e.response is not None:
            logger.error(f"Код ответа: {e.response.status_code}, Тело ответа: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"Неизвестная ошибка при транскрибации: {e}")
        return None