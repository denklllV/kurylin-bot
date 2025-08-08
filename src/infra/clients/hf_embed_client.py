# START OF FILE: src/infra/clients/hf_embed_client.py

import requests
from functools import lru_cache
from typing import List

from src.shared.logger import logger
from src.shared.config import HF_API_KEY # Используем тот же ключ, что и для Whisper

class EmbeddingClient:
    def __init__(self, model_name: str = 'sentence-transformers/all-MiniLM-L6-v2'):
        self.api_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{model_name}"
        self.headers = {"Authorization": f"Bearer {HF_API_KEY}"}
        logger.info(f"EmbeddingClient initialized for API model: {model_name}")

    @lru_cache(maxsize=1024)
    def get_embedding(self, text: str) -> List[float] | None:
        if not HF_API_KEY:
            logger.error("HF_API_KEY is missing. Cannot get embeddings.")
            return None
        
        try:
            # Нормализуем текст для лучшего качества
            text = text.replace("\n", " ")
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json={"inputs": text, "options": {"wait_for_model": True}}
            )
            response.raise_for_status()
            
            embedding = response.json()
            # Убеждаемся, что получили список чисел
            if isinstance(embedding, list) and all(isinstance(i, float) for i in embedding):
                return embedding
            else:
                logger.error(f"API returned unexpected data type for embedding: {type(embedding)}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create embedding via API for text: '{text[:50]}...'. Error: {e}")
            return None

# END OF FILE: src/infra/clients/hf_embed_client.py