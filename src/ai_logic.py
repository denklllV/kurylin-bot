# src/ai_logic.py
import requests
from openai import OpenAI
from .config import OPENROUTER_API_KEY, MODEL_NAME, HUGGINGFACE_API_KEY, STT_API_URL, KNOWLEDGE_BASE, logger

# Этот клиент остается для функции get_ai_response
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

def transcribe_voice(voice_path: str) -> str | None:
    """Отправляет аудиофайл в HuggingFace Inference API для транскрибации."""
    logger.info(f"Отправка файла {voice_path} в HuggingFace API...")
    try:
        headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
        
        # --- ИЗМЕНЕНИЕ ЗДЕСЬ: СНАЧАЛА ЧИТАЕМ ФАЙЛ, ПОТОМ ПЕРЕДАЕМ ДАННЫЕ ---
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

# --- Остальные функции остаются без изменений ---
def find_relevant_chunks(question: str, knowledge_base: str, max_chunks=5) -> str:
    chunks = knowledge_base.split('\n\n')
    question_keywords = set(question.lower().split())
    scored_chunks = []
    for chunk in chunks:
        chunk_words = set(chunk.lower().split())
        score = len(question_keywords.intersection(chunk_words))
        if score > 0:
            scored_chunks.append((score, chunk))
    
    scored_chunks.sort(reverse=True, key=lambda x: x[0])
    top_chunks = [chunk for score, chunk in scored_chunks[:max_chunks]]
    return "\n\n".join(top_chunks)

def get_ai_response(question: str) -> str:
    dynamic_context = find_relevant_chunks(question, KNOWLEDGE_BASE)
    
    system_prompt = (
        "Твоя роль — первоклассный юридический помощник. Твое имя — Вячеслав. "
        "Твоя речь — человечная, мягкая и эмпатичная. "
        "Твоя задача — кратко и в общих чертах разъяснять сложные юридические вопросы, донося только самую важную суть. "
        "Отвечай ТОЛЬКО на основе предоставленной ниже 'Базы знаний'. Если в ней нет ответа, вежливо сообщи, что не обладаешь этой информацией."
        "**СТРОГИЕ ПРАВИЛА:**"
        "1. **Краткость:** Твой ответ должен быть очень коротким, в идеале 1-2 абзаца."
        "2. **Никогда не представляйся**, если тебя не спросили напрямую 'Как тебя зовут?'. Сразу переходи к сути ответа."
        "3. **Никогда не упоминай** слова 'контекст' или 'база знаний'. Отвечай так, будто эта информация — твои собственные знания."
        "4. **Для форматирования** используй теги HTML: <b>...</b> для жирного, <i>...</i> для курсива. Для создания абзаца используй ОДНУ пустую строку."
    )
    
    user_prompt = f"База знаний:\n{dynamic_context}\n\nВопрос клиента: {question}"

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Ошибка при обращении к OpenRouter AI: {e}")
        return "К сожалению, произошла ошибка при обрашении к AI-сервису. Попробуйте позже."