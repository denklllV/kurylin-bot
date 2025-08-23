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
        # ИЗМЕНЕНИЕ: Жестко закодированный дисклеймер полностью удален.
        # Ответственность за его наличие теперь лежит на системном промпте.
        logger.info("AIService initialized with DYNAMIC system prompts.")

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
        
    def _build_rag_prompt(self, system_prompt: str, question: str, history: List[Message], rag_chunks: List[Dict[str, Any]], quiz_context: str = None) -> List[Dict[str, str]]:
        """Собирает полный промпт, используя предоставленный system_prompt."""
        
        current_system_prompt = system_prompt
        
        if quiz_context:
            current_system_prompt += (
                "\n\n**ВАЖНО:** У тебя есть дополнительная информация о клиенте, "
                "полученная из квиза. Обязательно используй её для более точного "
                "и персонализированного ответа.\n"
                f"--- КОНТЕКСТ КЛИЕНТА ---\n{quiz_context}\n--- КОНЕЦ КОНТЕКСТА ---"
            )

        messages = [{"role": "system", "content": current_system_prompt}]
        
        if history:
            history_text = "\n".join([f"{msg.role}: {msg.content}" for msg in history])
            messages.append({"role": "system", "content": f"Вот предыдущая часть нашего разговора:\n{history_text}"})

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

    def get_text_response(self, user_id: int, user_question: str, client_id: int) -> tuple[str, dict]:
        """Генерирует ответ, используя динамический системный промпт и контекст квиза для клиента."""
        start_time = time.time()
        
        system_prompt = self.repo.get_client_system_prompt(client_id)
        if not system_prompt:
            logger.error(f"Could not retrieve system prompt for client {client_id}. Using a safe fallback.")
            system_prompt = "Ты — полезный ассистент. Отвечай на вопросы кратко и по делу."

        history = self.repo.get_recent_messages(user_id, client_id)
        
        quiz_completed, quiz_results = self.repo.get_user_quiz_status(user_id, client_id)
        quiz_context = None
        if quiz_completed and isinstance(quiz_results, dict):
            logger.info(f"User {user_id} (client {client_id}) has quiz data. Adding it to context.")
            quiz_context = "\n".join([f"- {q}: {a}" for q, a in quiz_results.items()])

        rag_chunks = []
        
        messages_to_send = self._build_rag_prompt(system_prompt, user_question, history, rag_chunks, quiz_context)
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
        
        logger.info(f"Response generated for client {client_id} (Quiz context: {quiz_completed}). Time: {debug_info['processing_time']}.")
        
        # ИЗМЕНЕНИЕ: Возвращаем "чистый" ответ модели, без добавления дисклеймера.
        final_response = response_text
        return final_response, debug_info

    def transcribe_voice(self, audio_data: bytes) -> str | None:
        """Транскрибирует аудиоданные в текст."""
        return self.whisper_client.transcribe(audio_data)

# END OF FILE: src/app/services/ai_service.py