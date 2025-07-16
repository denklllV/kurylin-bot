# src/ai_logic.py

from openai import OpenAI

# Импортируем все необходимое из нашего центрального конфига
from .config import OPENROUTER_API_KEY, MODEL_NAME, KNOWLEDGE_BASE, logger

# Клиент создается один раз при загрузке этого модуля, а не при каждом вызове
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

def find_relevant_chunks(question: str, knowledge_base: str, max_chunks=5) -> str:
    """Находит наиболее релевантные части базы знаний по ключевым словам."""
    chunks = knowledge_base.split('\n\n')
    question_keywords = set(question.lower().split())
    scored_chunks = []
    for chunk in chunks:
        chunk_words = set(chunk.lower().split())
        score = len(question_keywords.intersection(chunk_words))
        if score > 0:
            scored_chunks.append((score, chunk))
    
    # Сортируем чанки по релевантности и берем лучшие
    scored_chunks.sort(reverse=True, key=lambda x: x[0])
    top_chunks = [chunk for score, chunk in scored_chunks[:max_chunks]]
    return "\n\n".join(top_chunks)

def get_ai_response(question: str) -> str:
    """Формирует запрос к AI на основе релевантных чанков и возвращает ответ."""
    # Шаг 1: Найти релевантный контекст внутри нашей базы знаний
    dynamic_context = find_relevant_chunks(question, KNOWLEDGE_BASE)
    
    # Шаг 2: Определить системный промпт (инструкцию для модели)
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
    
    # Шаг 3: Сформировать финальный промпт для пользователя
    user_prompt = f"База знаний:\n{dynamic_context}\n\nВопрос клиента: {question}"

    try:
        # Шаг 4: Отправить запрос к AI, используя extra_body для указания модели
        # Это изменение соответствует документации OpenRouter для данной модели
        completion = client.chat.completions.create(
            extra_body={
                "model": MODEL_NAME,
            },
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Ошибка при обращении к OpenRouter AI: {e}")
        return "К сожалению, произошла ошибка при обрашении к AI-сервису. Попробуйте позже."