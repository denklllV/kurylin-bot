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

# --- Логика поиска в базе знаний ---

def find_faq_answer(question: str) -> str | None:
    """Ищет точный ответ в базе FAQ по ключевым словам."""
    if not FAQ_DB: return None
    
    question_words = set(question.lower().split())
    best_match_score = 0
    best_answer = None

    for item in FAQ_DB:
        keywords = set(item.get('keywords', []))
        score = len(question_words.intersection(keywords))
        if score > best_match_score:
            best_match_score = score
            best_answer = item.get('answer')

    # Считаем совпадение успешным, если нашлось хотя бы 2 ключевых слова
    if best_match_score >= 2:
        logger.info(f"Найден быстрый ответ в FAQ (score: {best_match_score}).")
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
            
    if best_match_score >= 2:
        logger.info(f"Найдена релевантная цитата для контекста (score: {best_match_score}).")
        return best_quote_item
        
    return None

# --- Основной конвейер (pipeline) ответа ---

def get_ai_response(question: str) -> str:
    """Основная функция, реализующая трехступенчатую логику ответа."""
    # 1. Сначала ищем ответ в FAQ
    faq_answer = find_faq_answer(question)
    if faq_answer:
        return faq_answer

    # 2. Если в FAQ нет, ищем цитату для контекста
    quote_item = find_relevant_quote(question)
    
    # 3. Готовим контекст и системный промпт для AI
    context = ""
    if quote_item:
        context = f"Контекст для ответа (прямая цитата эксперта):\n{quote_item.get('quote', '')}"

    system_prompt = (
        "Твоя роль — первоклассный юрист-консультант по банкротству, твое имя — Вячеслав Курилин. "
        "Твоя речь — человечная, мягкая, эмпатичная и уверенная. Ты всегда на стороне клиента. "
        "Твоя задача — кратко и в общих чертах разъяснять сложные юридические вопросы, донося самую суть простыми словами."
        
        "**СТРОГИЕ ПРАВИЛА ТВОЕЙ ЛИЧНОСТИ:**\n"
        "1. **Никогда не представляйся**, если тебя не спросили напрямую 'Как тебя зовут?'. Сразу переходи к сути ответа.\n"
        "2. **Никогда не упоминай** слова 'контекст', 'база знаний', 'AI', 'модель' или 'цитата'. Отвечай так, будто эта информация — твои собственные знания и убеждения.\n"
        "3. **Краткость и ясность:** Твой ответ должен быть очень коротким, в идеале 1-2 абзаца. Избегай канцеляризмов.\n"
        "4. **Отвечай только по теме вопроса**, используя предоставленный контекст, если он есть. Если контекста нет или его недостаточно, дай общий полезный ответ по теме банкротства. Если вопрос совсем не по теме (не про долги, законы, финансы), вежливо сообщи, что специализируешься только на вопросах банкротства.\n"
        "5. **Используй HTML-теги** для форматирования: <b>...</b> для жирного, <i>...</i> для курсива."
    )
    
    user_prompt = f"{context}\n\nВопрос клиента: {question}"

    logger.info("Ответ не найден в базах, обращаюсь к AI-модели...")
    try:
        completion = client_openrouter.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=500,
            temperature=0.7
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

# --- Функция транскрибации голоса (остается без изменений) ---

def transcribe_voice(voice_path: str) -> str | None:
    """Отправляет аудиофайл в HuggingFace Inference API для транскрибации."""
    logger.info(f"Отправка файла {voice_path} в HuggingFace API...")
    try:
        # <--- ИЗМЕНЕНИЕ ЗДЕСЬ ---
        headers = {
            "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
            "Content-Type": "audio/mpeg"
        }
        # <--- КОНЕЦ ИЗМЕНЕНИЯ ---
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