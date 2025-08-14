# START OF FILE: src/app/services/ai_service.py

import time
import re
from typing import List, Dict, Any

from src.infra.clients.openrouter_client import OpenRouterClient
from src.infra.clients.hf_whisper_client import WhisperClient
from src.infra.clients.supabase_repo import SupabaseRepo
from src.domain.models import Message
from src.shared.logger import logger

def strip_all_html_tags(text: str) -> str:
    """Полностью удаляет все HTML-теги из текста."""
    if not text:
        return ""
    return re.sub(r'<.*?>', '', text)

class AIService:
    def __init__(
        self,
        or_client: OpenRouterClient,
        whisper_client: WhisperClient,
        repo: SupabaseRepo
    ):
        self.or_client = or_client
        self.whisper_client = whisper_client
        self.repo = repo
        self.system_prompt = self._load_system_prompt()
        self.disclaimer = "\n\nВажно: эта информация носит справочный характер и не является юридической консультацией."
        logger.info("AIService initialized (RAG is DISABLED).")

    def classify_text(self, text: str) -> str | None:
        """Классифицирует текст запроса по заданным категориям."""
        clean_text = " ".join(text.strip().split())
        if not clean_text:
            return "Нецелевой запрос"

        categories = [
            "Вопрос о стоимости",
            "Условия и процесс банкротства",
            "Последствия банкротства",
            "Общая консультация",
            "Нецелевой запрос"
        ]
        
        classifier_prompt = (
            "Твоя задача - классифицировать запрос пользователя. "
            "Проанализируй следующий текст и определи, к какой из этих категорий он относится:\n"
            f"- {', '.join(categories)}\n\n"
            "В своем ответе напиши ТОЛЬКО название одной категории и ничего больше. Будь точен."
        )

        messages = [
            {"role": "system", "content": classifier_prompt},
            {"role": "user", "content": clean_text}
        ]

        try:
            category = self.or_client.get_chat_completion(messages)
            clean_category = category.strip().replace('.', '')
            if clean_category in categories:
                logger.info(f"Text classified as '{clean_category}'.")
                return clean_category
            else:
                logger.warning(f"LLM returned an unknown category: '{category}'. Defaulting to 'Общая консультация'.")
                return "Общая консультация"
        except Exception as e:
            logger.error(f"Failed to classify text: {e}", exc_info=True)
            return "Общая консультация"

    def _load_system_prompt(self) -> str:
        """Загружает и возвращает системный промпт для основной задачи."""
        return (
            "Ты — юрист-консультант по банкротству Вячеслав Курилин. Твоя речь — человечная, мягкая и уверенная. Твоя задача — помочь клиенту.\n\n"
            "**СТРОГИЕ ПРАВИЛА ТВОЕГО ПОВЕДЕНИЯ:**\n"
            "1. **ТЕМАТИКА:** Ты отвечаешь **ТОЛЬКО** на вопросы, связанные с долгами, кредитами, финансами и процедурой банкротства в РФ. Если вопрос не по теме, ты **ОБЯЗАН** вежливо ответить: 'К сожалению, я специализируюсь только на вопросах, связанных с финансами и процедурой банкротства. Я не могу ответить на этот вопрос.'\n"
            "2. **БЕЗОПАСНОСТЬ:** Если предоставленной информации (в истории диалога или в базе знаний) недостаточно для точного ответа, или вопрос касается очень специфической, узкой ситуации, ты **ОБЯЗАН** ответить: 'Чтобы дать точный ответ по вашей ситуации, мне недостаточно информации. Рекомендую вам напрямую связаться со специалистом для детального разбора.'\n"
            "3. **ПРИОРИТЕТ КОНТЕКСТА:** Если факты из базы знаний (RAG) противоречат предыдущей истории диалога, **приоритет всегда у фактов из базы знаний**.\n"
            "4. **ЧИСТОТА ОТВЕТА:** В твоем ответе не должно быть никаких служебных слов вроде 'Ответ:'. Сразу начинай отвечать по существу.\n"
        )
        
    def _build_rag_prompt(self, question: str, history: List[Message], rag_chunks: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Собирает полный промпт для LLM, включая историю и (если есть) RAG-контекст."""
        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            history_text = "\n".join([f"{msg.role}: {msg.content}" for msg in history])
            messages.append({"role": "system", "content": f"Вот предыдущая часть нашего разговора:\n{history_text}"})
        # RAG отключен, поэтому этот блок никогда не выполнится, но мы оставляем его для будущего
        if rag_chunks:
            rag_context = "\n---\n".join([chunk.get('content', '') for chunk in rag_chunks])
            user_prompt_text = (
                "Используя приведённые ниже факты из моей базы знаний, ответь на вопрос клиента.\n"
                "Твой ответ должен основываться в первую очередь на этих фактах.\n\n"
                f"--- ФАКТЫ ---\n{rag_context}\n--- КОНЕЦ ФАКТОВ ---\n\n"
                f"Вопрос клиента: «{question}»"
            )
        else:
            user_prompt_text = f"Вопрос клиента: «{question}»"
        messages.append({"role": "user", "content": user_prompt_text})
        return messages

    def get_text_response(self, user_id: int, user_question: str) -> tuple[str, dict]:
        """Генерирует ответ БЕЗ RAG-контекста."""
        start_time = time.time()
        history = self.repo.get_recent_messages(user_id)
        
        # RAG отключен, всегда пустой список чанков
        rag_chunks = []
        
        messages_to_send = self._build_rag_prompt(user_question, history, rag_chunks)
        raw_response_text = self.or_client.get_chat_completion(messages_to_send)
        response_text = strip_all_html_tags(raw_response_text)
        end_time = time.time()

        debug_info = {
            "user_question": user_question,
            "llm_response": response_text,
            "final_prompt": messages_to_send,
            "rag_chunks": rag_chunks,
            "conversation_history": [msg.to_dict() for msg in history],
            "processing_time": f"{end_time - start_time:.2f}s"
        }
        
        logger.info(f"Response generated without RAG. Time: {debug_info['processing_time']}.")
        
        final_response = response_text + self.disclaimer
        return final_response, debug_info

    def transcribe_voice(self, audio_data: bytes) -> str | None:
        """Транскрибирует аудиоданные в текст."""
        return self.whisper_client.transcribe(audio_data)

# END OF FILE: src/app/services/ai_service.py