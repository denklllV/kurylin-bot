# scripts/download_model.py
import os
import sys
from sentence_transformers import SentenceTransformer

# Этот блок нужен, чтобы скрипт мог найти модуль config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Мы не можем использовать logger здесь, так как он настроен в config,
# который может быть недоступен на этом этапе сборки. Используем print.
print("--- Запуск скрипта для скачивания модели ---")

# Импортируем только то, что нужно
from src.config import EMBEDDING_MODEL_NAME

CACHE_DIR = "/app/cache"

print(f"Скачиваю модель {EMBEDDING_MODEL_NAME} в папку {CACHE_DIR}...")

# Эта команда скачает модель и сохранит ее в указанную папку
SentenceTransformer(EMBEDDING_MODEL_NAME, cache_folder=CACHE_DIR)

print("--- Модель успешно скачана ---")