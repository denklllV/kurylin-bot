# START OF FILE: scripts/vectorize_knowledge_base.py

import json
import os
import sys
import time
from dotenv import load_dotenv
from pathlib import Path

# --- НАДЁЖНЫЙ ШАБЛОН ЗАГРУЗКИ ---
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env", override=True)

REQUIRED_VARS = ["SUPABASE_URL", "SUPABASE_KEY"]
for var in REQUIRED_VARS:
    if not os.getenv(var):
        raise RuntimeError(f"{var} is missing. Check your .env file.")
# ------------------------------------

# --- Импорты после настройки путей ---
from sentence_transformers import SentenceTransformer
from src.infra.clients.supabase_repo import SupabaseRepo
from src.shared.logger import logger

def load_data_from_json() -> list[dict]:
    """Загружает, объединяет и фильтрует данные из JSON-источников."""
    prepared_data = []
    # ... (логика без изменений) ...
    try:
        with open('data/faq.json', 'r', encoding='utf-8') as f:
            faq_data = json.load(f)
        for item in faq_data:
            content = f"Вопрос: {item.get('question', '')}\nОтвет: {item.get('answer', '')}"
            if content.strip(): prepared_data.append({"content": content, "source": "FAQ"})
        logger.info(f"Загружено {len(faq_data)} записей из FAQ.")
    except FileNotFoundError:
        logger.warning("Файл faq.json не найден, пропущен.")
    try:
        with open('data/interviews.json', 'r', encoding='utf-8') as f:
            interviews_data = json.load(f)
        for item in interviews_data:
            content = item.get('quote', '')
            if content.strip(): prepared_data.append({"content": content, "source": f"Цитата из «{item.get('source_name', '')}»"})
        logger.info(f"Загружено {len(interviews_data)} записей из Интервью.")
    except FileNotFoundError:
        logger.warning("Файл interviews.json не найден, пропущен.")
    return prepared_data


def run_vectorization():
    """
    Полностью очищает базу знаний, локально вычисляет эмбеддинги
    и загружает их в Supabase.
    """
    logger.info("--- Starting LOCAL Vectorization and Upload ---")
    
    # 1. Загружаем данные из JSON
    data_to_process = load_data_from_json()
    if not data_to_process:
        logger.warning("No data found. Aborting."); return

    # 2. Загружаем локальную модель
    model_name = 'cointegrated/rubert-tiny2'
    logger.info(f"Loading local SentenceTransformer model: {model_name}...")
    try:
        model = SentenceTransformer(model_name, device='cpu')
        logger.info("Model loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load model: {e}", exc_info=True)
        return
        
    # 3. Вычисляем эмбеддинги локально
    contents = [item['content'] for item in data_to_process]
    logger.info(f"Encoding {len(contents)} documents locally...")
    embeddings = model.encode(contents, show_progress_bar=True, convert_to_numpy=True)
    logger.info("Encoding complete.")
    
    # 4. Подготавливаем записи для загрузки
    records_to_upload = [
        {'content': item['content'], 'embedding': emb.tolist(), 'source': item['source']}
        for item, emb in zip(data_to_process, embeddings)
    ]
    
    # 5. Очищаем и загружаем в Supabase
    repo = SupabaseRepo()
    logger.info("Clearing the 'knowledge_base' table in Supabase...")
    repo.client.table('knowledge_base').delete().neq('id', 0).execute()
    
    logger.info(f"Upserting {len(records_to_upload)} records to Supabase...")
    repo.client.table('knowledge_base').insert(records_to_upload).execute()
    
    logger.info("✅ Knowledge base has been successfully vectorized and uploaded!")

if __name__ == "__main__":
    run_vectorization()

# END OF FILE: scripts/vectorize_knowledge_base.py