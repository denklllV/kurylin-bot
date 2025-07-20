# src/ai_logic.py
import json
import requests
import os # <-- НОВЫЙ ИМПОРТ
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from .config import OPENROUTER_API_KEY, MODEL_NAME, HUGGINGFACE_API_KEY, STT_API_URL, EMBEDDING_MODEL_NAME, logger
from .database import find_similar_chunks

# --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
# Указываем путь для кэша внутри нашей рабочей директории
CACHE_DIR = "/app/cache"
os.makedirs(CACHE_DIR, exist_ok=True)
# --- КОНЕЦ ИЗМЕНЕНИЯ ---

# --- Инициализация клиентов и моделей при старте ---
client_openrouter = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

logger.info(f"Загрузка модели эмбеддингов: {EMBEDDING_MODEL_NAME}...")
# --- ИЗМЕНЕНИЕ ЗДЕСЯ ---
embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME, device='cpu', cache_folder=CACHE_DIR)
# --- КОНЕЦ ИЗМЕНЕНИЯ ---
logger.info("Модель эмбеддингов успешно загружена.")
# --- Конец блока инициализации ---


def get_ai_response(question: str) -> str:
    """
    Основная функция генерации ответа с использованием семантического поиска.
    """
    # Шаг 1: Векторизуем вопрос пользователя
    question_embedding = embedding_model.encode(question).tolist()
    
    # Шаг 2: Ищем релевантные фрагменты в базе знаний
    similar_chunks = find_similar_chunks(question_embedding)
    
    # Шаг 3: Готовим контекст и системный промпт для LLM
    context = "Контекста не найдено."
    if similar_chunks:
        context_parts = [chunk['content'] for chunk in similar_chunks]
        context = "\n\n---\n\n".join(context_parts)

    system_prompt = (
        "Твоя роль — первоклассный юрист-консультант по банкротству, твое имя — Вячеслав Курилин. "
        "Твоя речь — человечная, мягкая, эмпатичная и уверенная. Ты всегда на стороне клиента. "
        "Твоя задача — дать четкий и полезный ответ на вопрос клиента, основываясь **исключительно** на предоставленном ниже контексте."
        
        "**СТРОГИЕ ПРАВИЛА ТВОЕЙ ЛИЧНОСТИ И ПОВЕДЕНИЯ:**\n"
        "1. **Никогда не выдумывай информацию.** Твой ответ должен быть прямым пересказом или обобщением фактов из контекста. Не добавляй ничего от себя.\n"
        "2. **Если контекст нерелевантен вопросу** или недостаточен для ответа, вежливо сообщи, что специализируешься только на вопросах банкротства физических лиц в РФ и не можешь ответить на этот вопрос.\n"
        "3. **Никогда не упоминай** слова 'контекст', 'база знаний', 'AI', 'модель' или 'источник'. Отвечай так, будто эта информация — твои собственные экспертные знания.\n"
        "4. **Никогда не представляйся**, если тебя не спросили напрямую. Сразу переходи к сути ответа.\n"
        "5. **Краткость и ясность:** Твой ответ должен быть очень коротким, в идеале 1-2 абзаца. Избегай канцеляризмов и воды.\n"
        "6. **Используй HTML-теги** для форматирования: <b>...</b> для жирного, <i>...</i> для курсива, если это уместно."
    )
    
    user_prompt = f"Контекст:\n{context}\n\nВопрос клиента: {question}\n\nОтвет:"

    logger.info("Контекст найден, обращаюсь к AI-модели для генерации ответа...")
    try:
        completion = client_openrouter.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=500,
            temperature=0.4 # Снижаем температуру для более строгого следования контексту
        )
        ai_answer = completion.choices[0].message.content
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