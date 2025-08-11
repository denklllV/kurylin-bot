# START OF FILE: src/app/services/ai_service.py

import time
from typing import List, Dict, Any

from src.infra.clients.openrouter_client import OpenRouterClient
from src.infra.clients.hf_whisper_client import WhisperClient
# ИЗМЕНЕНИЕ: Возвращаем импорт нашего HF API клиента
from src.infra.clients.hf_embed_client import EmbeddingClient
from src.infra.clients.supabase_repo import SupabaseRepo
from src.domain.models import Message
from src.shared.logger import logger

class AIService:
    def __init__(
        self,
        or_client: OpenRouterClient,
        whisper_client: WhisperClient,
        # ИЗМЕНЕНИЕ: Указываем правильный тип клиента
        embed_client: EmbeddingClient,
        repo: SupabaseRepo
    ):
        self.or_client = or_client
        self.whisper_client = whisper_client
        self.embed_client = embed_client
        self.repo = repo
        self.system_prompt = self._load_system_prompt()
        self.disclaimer = "\n\n<i><b>Важно:</b> эта информация носит справочный характер и не является юридической консультацией.</i>"
        logger.info("AIService initialized.")

    def _load_system_prompt(self) -> str:
        # ... (код без изменений) ...
        return (
            "Ты — юрист-консультант по банкротству Вячеслав Курилин. Твоя речь — человечная, мягкая и уверенная. Твоя задача — помочь клиенту.\n\n"
            "**СТРОГИЕ ПРАВИЛА ТВОЕГО ПОВЕДЕНИЯ:**\n"
            "1. **ТЕМАТИКА:** Ты отвечаешь **ТОЛЬКО** на вопросы, связанные с долгами, кредитами, финансами и процедурой банкротства в РФ. Если вопрос не по теме, ты **ОБЯЗАН** вежливо ответить: 'К сожалению, я специализируюсь только на вопросах, связанных с финансами и процедурой банкротства. Я не могу ответить на этот вопрос.'\n"
            "2. **БЕЗОПАСНОСТЬ:** Если предоставленной информации (в истории диалога или в базе знаний) недостаточно для точного ответа, или вопрос касается очень специфической, узкой ситуации, ты **ОБЯЗАН** ответить: 'Чтобы дать точный ответ по вашей ситуации, мне недостаточно информации. Рекомендую вам напрямую связаться со специалистом для детального разбора.'\n"
            "3. **ПРИОРИТЕТ КОНТЕКСТА:** Если факты из базы знаний (RAG) противоречат предыдущей истории диалога, **приоритет всегда у фактов из базы знаний**.\n"
            "4. **ФОРМАТИРОВАНИЕ:** Используй **ТОЛЬКО** следующие HTML-теги: `<b>` для жирного, `<i>` для курсива, `<a>` для ссылок. **СТРОГО ЗАПРЕЩЕНО** использовать любые другие теги, особенно `<ul>`, `<li>`, `<div>`, `<p>`.\n"
            "5. **ЧИСТОТА ОТВЕТА:** В твоем ответе не должно быть никаких служебных слов вроде 'Ответ:'. Сразу начинай отвечать по существу.\n"
        )
        
    def _build_rag_prompt(
        self,
        question: str,
        history: List[Message],
        rag_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        # ... (код без изменений) ...
        messages = [{"role": "system", "content": self.system_prompt}]
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

    def get_text_response(self, user_id: int, user_question: str) -> tuple[str, dict]:
        start_time = time.time()
        
        history = self.repo.get_recent_messages(user_id)
        
        embedding = self.embed_client.get_embedding(user_question)
        
        rag_chunks = []
        if embedding:
            rag_chunks = self.repo.find_similar_chunks(embedding)
        
        messages_to_send = self._build_rag_prompt(user_question, history, rag_chunks)
        response_text = self.or_client.get_chat_completion(messages_to_send)
        
        end_time = time.time()

        debug_info = {
            "user_question": user_question,
            "llm_response": response_text,
            "final_prompt": messages_to_send,
            "rag_chunks": rag_chunks,
            # ИСПРАВЛЕНИЕ: Теперь этот вызов будет работать благодаря методу to_dict()
            "conversation_history": [msg.to_dict() for msg in history],
            "processing_time": f"{end_time - start_time:.2f}s"
        }

        scores = [f"{chunk.get('similarity', 0):.4f}" for chunk in rag_chunks]
        logger.info(
            f"Response generated. Time: {debug_info['processing_time']}. "
            f"RAG chunks: {len(rag_chunks)} (Scores: {', '.join(scores) if scores else 'N/A'})."
        )
        
        final_response = response_text + self.disclaimer
        return final_response, debug_info

    def transcribe_voice(self, audio_data: bytes) -> str | None:
        return self.whisper_client.transcribe(audio_data)

# END OF FILE: src/app/services/ai_service.py