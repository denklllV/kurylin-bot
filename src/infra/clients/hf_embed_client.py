# START OF FILE: src/infra/clients/hf_embed_client.py

import requests
from functools import lru_cache
from typing import List

from src.shared.logger import logger
from src.shared.config import HF_API_KEY

class EmbeddingClient:
    def __init__(self, model_name: str = 'cointegrated/rubert-tiny2'):
        # ИСПРАВЛЕНИЕ: Возвращаем самый базовый и правильный URL для вызова модели
        self.api_url = f"https://api-inference.huggingface.co/models/{model_name}"
        self.headers = {"Authorization": f"Bearer {HF_API_KEY}"}
        logger.info(f"EmbeddingClient initialized for HF Inference API: {self.api_url}")

    @lru_cache(maxsize=1024)
    def get_embedding(self, text: str) -> List[float] | None:
        if not HF_API_KEY:
            logger.error("HF_API_KEY is missing. Cannot get embeddings.")
            return None
        
        try:
            input_text = text.replace("\n", " ")
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json={
                    "inputs": [input_text], # Отправляем как список из одного элемента
                    "options": {"wait_for_model": True}
                }
            )
            response.raise_for_status()
            
            response_data = response.json()
            
            # API для sentence-transformer моделей возвращает [[...]]
            if isinstance(response_data, list) and response_data and isinstance(response_data[0], list):
                embedding = response_data[0][0] # В некоторых случаях вложенность тройная
                if isinstance(embedding, list) and all(isinstance(i, float) for i in embedding):
                    return embedding

            # Если структура [[...]] не подошла, пробуем [[]]
            if isinstance(response_data, list) and response_data and isinstance(response_data[0], list) and isinstance(response_data[0][0], list):
                 embedding = response_data[0][0][0]
                 if isinstance(embedding, list) and all(isinstance(i, float) for i in embedding):
                    return embedding


            logger.error(f"API returned unexpected data structure for embedding: {response_data}")
            return None
                
        except Exception as e:
            logger.error(f"Failed to create embedding via API for text: '{text[:50]}...'. Error: {e}")
            return None

# END OF FILE: src/infra/clients/hf_embed_client.py