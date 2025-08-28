# path: src/infra/clients/hf_embed_client.py
import requests
from functools import lru_cache
from typing import List

from src.shared.logger import logger
from src.shared.config import HF_API_KEY

class EmbeddingClient:
    def __init__(self, model_name: str = 'cointegrated/rubert-tiny2'):
        # ИСПРАВЛЕНИЕ: Используем более надежный и общий эндпоинт /models/
        self.api_url = f"https://api-inference.huggingface.co/models/{model_name}"
        self.headers = {"Authorization": f"Bearer {HF_API_KEY}"}
        logger.info(f"EmbeddingClient (API) initialized for model: {model_name}")

    @lru_cache(maxsize=1024)
    def get_embedding(self, text: str) -> List[float] | None:
        """Получает векторное представление (эмбеддинг) для текста через HF Inference API."""
        if not HF_API_KEY:
            logger.error("HF_API_KEY is missing. Cannot get embeddings via API.")
            return None
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json={
                    "inputs": [text.replace("\n", " ")],
                    "options": {"wait_for_model": True}
                }
            )
            response.raise_for_status()
            response_data = response.json()
            
            # API для sentence-transformer моделей возвращает [[...]]
            if isinstance(response_data, list) and response_data and isinstance(response_data[0], list):
                embedding = response_data[0][0]
                if isinstance(embedding, list) and all(isinstance(i, float) for i in embedding):
                    return embedding

            logger.error(f"HF API returned unexpected data structure for embedding: {response_data}")
            return None
                
        except Exception as e:
            logger.error(f"Failed to create embedding via API for text: '{text[:50]}...'. Error: {e}", exc_info=True)
            return None
# path: src/infra/clients/hf_embed_client.py