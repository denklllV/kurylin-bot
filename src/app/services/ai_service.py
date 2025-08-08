# START OF FILE: src/app/services/ai_service.py

from typing import List

from src.infra.clients.openrouter_client import OpenRouterClient
from src.infra.clients.hf_whisper_client import WhisperClient
from src.domain.models import Message
from src.shared.logger import logger

class AIService:
    def __init__(self, or_client: OpenRouterClient, whisper_client: WhisperClient):
        self.or_client = or_client
        self.whisper_client = whisper_client
        self.system_prompt = self._load_system_prompt()
        logger.info("AIService initialized.")

    def _load_system_prompt(self) -> str:
        # В будущем этот промпт можно будет вынести в файл, как в вашей схеме
        return (
            "Ты — юрист-консультант по банкротству Вячеслав Курилин. Твоя речь — человечная, мягкая и уверенная. Твоя задача — помочь клиенту.\n\n"
            "**СТРОГИЕ ПРАВИЛА ТВОЕГО ПОВЕДЕНИЯ:**\n"
            "1. **ТЕМАТИКА:** Ты отвечаешь **ТОЛЬКО** на вопросы, связанные с долгами, кредитами, финансами и процедурой банкротства в РФ. Если вопрос не по теме, ты **ОБЯЗАН** вежливо ответить: 'К сожалению, я специализируюсь только на вопросах, связанных с финансами и процедурой банкротства. Я не могу ответить на этот вопрос.'\n"
            "2. **КРАТКОСТЬ:** Твой ответ должен быть коротким, 2-3 небольших абзаца.\n"
            "3. **ФОРМАТИРОВАНИЕ:** Используй **только HTML-теги**: `<b>...</b>` для жирного и `<i>...</i>` для курсива. **Никогда не используй Markdown**.\n"
            "4. **ЧИСТОТА ОТВЕТА:** В твоем ответе не должно быть никаких служебных слов вроде 'Ответ:'. Сразу начинай отвечать по существу.\n"
            "5. **ЭТИКЕТ:** Никогда не представляйся. Никогда не упоминай слова 'контекст', 'база знаний', 'AI', 'модель'."
        )

    def get_text_response(self, user_question: str) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_question}
        ]
        # Пока мы не используем RAG или память, логика простая
        response_text = self.or_client.get_chat_completion(messages)
        return response_text

    def transcribe_voice(self, audio_data: bytes) -> str | None:
        return self.whisper_client.transcribe(audio_data)

# END OF FILE: src/app/services/ai_service.py