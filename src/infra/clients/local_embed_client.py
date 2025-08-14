# START OF FILE: src/infra/clients/local_embed_client.py

from sentence_transformers import SentenceTransformer
from typing import List
from functools import lru_cache

from src.shared.logger import logger

class LocalEmbeddingClient:
    def __init__(self, model_name: str = 'cointegrated/rubert-tiny2'):
        try:
            logger.info(f"Loading local SentenceTransformer model: {model_name}...")
            # Загружаем модель в память при инициализации
            self.model = SentenceTransformer(model_name)
            logger.info("Local sentence model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer model: {e}", exc_info=True)
            self.model = None

    @lru_cache(maxsize=1024)
    def get_embedding(self, text: str) -> List[float] | None:
        if not self.model:
            logger.error("Embedding model is not loaded. Cannot get embedding.")
            return None
        
        try:
            input_text = text.replace("\n", " ")
            embedding = self.model.encode(input_text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Failed to create local embedding for text: '{text[:50]}...'. Error: {e}")
            return None

# END OF FILE: src/infra/clients/local_embed_client.py