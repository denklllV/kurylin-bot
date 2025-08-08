# START OF FILE: src/infra/clients/hf_embed_client.py

from sentence_transformers import SentenceTransformer
from functools import lru_cache
from typing import List

from src.shared.logger import logger

class EmbeddingClient:
    def __init__(self, model_name: str = 'sentence-transformers/all-MiniLM-L6-v2'):
        """
        Инициализирует клиент для создания эмбеддингов.
        Модель будет скачана и закэширована при первом использовании.
        """
        try:
            logger.info(f"Initializing EmbeddingClient with model: {model_name}...")
            self.model = SentenceTransformer(model_name)
            logger.info("SentenceTransformer model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer model: {e}")
            self.model = None

    @lru_cache(maxsize=1024) # Кэшируем результаты для одинаковых текстов
    def get_embedding(self, text: str) -> List[float] | None:
        """
        Создает векторное представление (эмбеддинг) для одного текста.
        """
        if not self.model:
            logger.error("Embedding model is not available.")
            return None
        
        try:
            # Нормализуем текст для лучшего кэширования и качества
            text = text.replace("\n", " ")
            embedding = self.model.encode(text, convert_to_numpy=False)
            return embedding
        except Exception as e:
            logger.error(f"Failed to create embedding for text: '{text[:50]}...'. Error: {e}")
            return None

# END OF FILE: src/infra/clients/hf_embed_client.py