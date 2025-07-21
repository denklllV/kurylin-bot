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
        if not keywords: continue
        
        score = len(question_words.intersection(keywords))
        if score > best_match_score:
            best_match_score = score
            best_answer = item.get('answer')

    # Считаем совпадение успешным, если нашлось хотя бы 3 ключевых слова
    if best_match_score >= 3:
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
        if not keywords: continue
            
        score = len(question_words.intersection(keywords))
        if score > best_match_score:
            best_match_score = score
            best_quote_item = item
            
    # Возвращаем цитату, даже если найдено всего 2 ключевых слова
    if best_match_score >= 2:
        logger.info(f"Найдена релевантная цитата для контекста (score: {best_match_score}).")
        return best_quote_item
        
    return None

# --- "УМНЫЙ" ПРОМПТ-ИНЖЕНЕР ---

def get_ai_response(question: str) -> str:
    """
    Основная функция, реализующая динамическое конструирование промпта.
    """
    faq_answer = find_faq_answer(question)
    quote_item = None
    
    system_prompt = (
        "Твоя роль — первоклассный юрист-консультант по банкротству, твое имя — Вячеслав Курилин. "
        "Твоя речь — человечная, мягкая, эмпатичная и уверенная. Твоя задача — дать четкий и полезный ответ на вопрос клиента.\n\n"
        "**ОСНОВНЫЕ ПРАВИЛА:**\n"
        # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
        "1. **КРАТКОСТЬ:** Твой ответ должен быть коротким и по существу, в идеале 2-3 небольших абзаца. **Никогда не пиши длинных текстов.** Твоя цель — дать основную информацию, а не полную консультацию.\n"
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---
        "2. **ТОН:** Всегда придерживайся экспертного, но доброжелательного и уверенного тона, без давления.\n"
        "3. **ЧЕСТНОСТЬ:** Никогда не упоминай слова 'контекст', 'база знаний', 'AI', 'модель' или 'цитата'.\n"
        "4. **ЭТИКЕТ:** Никогда не представляйся, если не спросили напрямую. Сразу переходи к сути.\n"
        "5. **ФОРМАТИРОВАНИЕ:** Используй HTML-теги для форматирования: <b>...</b> для жирного, <i>...</i> для курсива."
    )

    if faq_answer:
        # Сценарий 1: Найден точный ответ в FAQ. Стилизуем его.
        logger.info("Промпт-инженер: Сценарий 1 (Стилизация FAQ).")
        user_prompt = (
            f"Вопрос клиента: «{question}»\n\n"
            f"Вот точный факт из нашей базы знаний:\n---ФАКТ---\n{faq_answer}\n---КОНЕЦ ФАКТА---\n\n"
            f"Твоя задача: Перепиши этот факт своими словами, сохранив всю суть, но придав ему человечный и эмпатичный тон, чтобы полностью ответить на вопрос клиента. "
            f"Можешь начать с фразы вроде 'Смотрите, ситуация следующая...' или подобной, если это уместно."
        )
    else:
        quote_item = find_relevant_quote(question)
        if quote_item:
            # Сценарий 2: Найден релевантный пример (цитата). Используем ее как основу.
            logger.info("Промпт-инженер: Сценарий 2 (Ответ на основе цитаты).")
            user_prompt = (
                f"Вопрос клиента: «{question}»\n\n"
                f"Вот контекст и пример стиля ответа из интервью эксперта:\n---КОНТЕКСТ---\n«{quote_item.get('quote', '')}»\n---КОНЕЦ КОНТЕКСТА---\n\n"
                f"Твоя задача: Используя факты и стиль из этого контекста, дай прямой и ясный ответ на вопрос клиента."
            )
        else:
            # Сценарий 3: Ничего не найдено. Общий вопрос к LLM.
            logger.info("Промпт-инженер: Сценарий 3 (Общий вопрос).")
            user_prompt = f"Вопрос клиента: «{question}»\n\nКонтекста в базе знаний не найдено. Ответь на вопрос, основываясь на своих общих знаниях по теме банкротства в РФ."

    try:
        completion = client_openrouter.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            # Оставляем max_tokens как "предохранитель", но модель должна остановиться сама раньше
            max_tokens=800, 
            temperature=0.7
        )
        ai_answer = completion.choices[0].message.content
        
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
    # Эта функция остается без изменений
    # ... (код функции)
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
        logger.error(f"Ошибка HTTP-запроса при транскрибиции: {e}")
        if e.response is not None:
            logger.error(f"Код ответа: {e.response.status_code}, Тело ответа: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"Неизвестная ошибка при транскрибиции: {e}")
        return None