# START OF FILE: src/infra/clients/hf_embed_client.py

import requests
from functools import lru_cache
from typing import List

from src.shared.logger import logger
from src.shared.config import HF_API_KEY

class EmbeddingClient:
    # Оставляем эту модель, так как она хорошая, но меняем способ обращения к ней
    def __init__(self, model_name: str = 'intfloat/multilingual-e5-small'):
        # ИСПРАВЛЕНИЕ: Используем прямой эндпоинт модели, а не пайплайн
        self.api_url = f"https://api-inference.huggingface.co/models/{model_name}"
        self.headers = {"Authorization": f"Bearer {HF_API_KEY}"}
        logger.info(f"EmbeddingClient initialized for API model: {model_name}")

    @lru_cache(maxsize=1024)
    def get_embedding(self, text: str) -> List[float] | None:
        if not HF_API_KEY:
            logger.error("HF_API_KEY is missing. Cannot get embeddings.")
            return None
        
        try:
            # Модели e5 требуют добавления "query: "
            input_text = "query: " + text.replace("\n", " ")
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json={"inputs": input_text} # Упрощаем тело запроса
            )
            response.raise_for_status()
            
            embedding_list = response.json()
            # Ответ от прямого эндпоинта имеет другую структуру
            if isinstance(embedding_list, list) and embedding_list and isinstance(embedding_list[0], list):
                embedding = embedding_list[0]
                if isinstance(embedding, list) and all(isinstance(i, float) for i in embedding):
                    return embedding

            logger.error(f"API returned unexpected data structure: {embedding_list}")
            return None
                
        except Exception as e:
            logger.error(f"Failed to create embedding via API for text: '{text[:50]}...'. Error: {e}")
            return None

# END OF FILE: src/infra/clients/hf_embed_client.py