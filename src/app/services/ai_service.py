# START OF FILE: src/app/services/ai_service.py

from typing import List

from src.infra.clients.openrouter_client import OpenRouterClient
from src.infra.clients.hf_whisper_client import WhisperClient
from src.infra.clients.hf_embed_client import EmbeddingClient
from src.infra.clients.supabase_repo import SupabaseRepo
from src.domain.models import Message
from src.shared.logger import logger

class AIService:
    def __init__(
        self,
        or_client: OpenRouterClient,
        whisper_client: WhisperClient,
        embed_client: EmbeddingClient,
        repo: SupabaseRepo
    ):
        self.or_client = or_client
        self.whisper_client = whisper_client
        self.embed_client = embed_client
        self.repo = repo
        self.system_prompt = self._load_system_prompt()
        logger.info("AIService initialized with all dependencies.")

    def _load_system_prompt(self) -> str:
        # ИСПРАВЛЕНИЕ: Ужесточаем правила форматирования
        return (
            "Ты — юрист-консультант по банкротству Вячеслав Курилин. Твоя речь — человечная, мягкая и уверенная. Твоя задача — помочь клиенту.\n\n"
            "**СТРОГИЕ ПРАВИЛА ТВОЕГО ПОВЕДЕНИЯ:**\n"
            "1. **ТЕМАТИКА:** Ты отвечаешь **ТОЛЬКО** на вопросы, связанные с долгами, кредитами, финансами и процедурой банкротства в РФ. Если вопрос не по теме, ты **ОБЯЗАН** вежливо ответить: 'К сожалению, я специализируюсь только на вопросах, связанных с финансами и процедурой банкротства. Я не могу ответить на этот вопрос.'\n"
            "2. **КРАТКОСТЬ:** Твой ответ должен быть коротким, 2-3 небольших абзаца.\n"
            "3. **ФОРМАТИРОВАНИЕ:** Используй **ТОЛЬКО** следующие HTML-теги: `<b>` для жирного, `<i>` для курсива, `<a>` для ссылок. **СТРОГО ЗАПРЕЩЕНО** использовать любые другие теги, особенно `<ul>`, `<li>`, `<div>`, `<p>`.\n"
            "4. **ЧИСТОТА ОТВЕТА:** В твоем ответе не должно быть никаких служебных слов вроде 'Ответ:'. Сразу начинай отвечать по существу.\n"
            "5. **ЭТИКЕТ:** Никогда не представляйся. Никогда не упоминай слова 'контекст', 'база знаний', 'AI', 'модель'."
        )

    def _build_rag_prompt(
        self,
        question: str,
        history: List[Message],
        rag_chunks: List[dict]
    ) -> List[dict]:
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

    def get_text_response(self, user_id: int, user_question: str) -> str:
        history = self.repo.get_recent_messages(user_id)
        embedding = self.embed_client.get_embedding(user_question)
        rag_chunks = []
        if embedding:
            rag_chunks = self.repo.find_similar_chunks(embedding)
        messages_to_send = self._build_rag_prompt(user_question, history, rag_chunks)
        response_text = self.or_client.get_chat_completion(messages_to_send)
        return response_text

    def transcribe_voice(self, audio_data: bytes) -> str | None:
        return self.whisper_client.transcribe(audio_data)

# END OF FILE: src/app/services/ai_service.py