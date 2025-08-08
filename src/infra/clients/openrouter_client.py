# START OF FILE: src/infra/clients/openrouter_client.py

from openai import OpenAI
from typing import List, Dict

from src.shared.logger import logger
from src.shared.config import OPENROUTER_API_URL, OPENROUTER_API_KEY, PUBLIC_APP_URL, LLM_MODEL_NAME
from src.domain.models import Message

class OpenRouterClient:
    def __init__(self, app_title="Vyacheslav Kurilin AI Assistant"):
        self.client = OpenAI(base_url=OPENROUTER_API_URL, api_key=OPENROUTER_API_KEY)
        self.headers = {
            "HTTP-Referer": PUBLIC_APP_URL,
            "X-Title": app_title,
        }
        logger.info("OpenRouter client initialized.")

    def get_chat_completion(self, messages: List[Dict]) -> str:
        try:
            logger.info(f"Requesting chat completion with model {LLM_MODEL_NAME}...")
            completion = self.client.chat.completions.create(
                extra_headers=self.headers,
                model=LLM_MODEL_NAME,
                messages=messages,
                max_tokens=1024,
                temperature=0.7
            )
            response_text = completion.choices[0].message.content
            logger.info("Chat completion received successfully.")
            return response_text
        except Exception as e:
            logger.error(f"Error getting chat completion from OpenRouter: {e}")
            return "К сожалению, произошла техническая ошибка при обработке вашего вопроса. Пожалуйста, попробуйте позже."

# END OF FILE: src/infra/clients/openrouter_client.py