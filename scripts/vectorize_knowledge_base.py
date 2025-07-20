# scripts/vectorize_knowledge_base.py
import json
import os
import sys
from dotenv import load_dotenv

# --- Начальная настройка для импорта модулей из src ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

dotenv_path = os.path.join(project_root, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    print("Внимание: .env файл не найден, скрипт может не работать без переменных окружения.")

# --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
# Указываем путь для кэша внутри нашей рабочей директории
CACHE_DIR = os.path.join(project_root, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
# --- КОНЕЦ ИЗМЕНЕНИЯ ---

from sentence_transformers import SentenceTransformer
from supabase import create_client, Client

from src.config import logger, SUPABASE_URL, SUPABASE_KEY, EMBEDDING_MODEL_NAME

def get_db_client() -> Client:
    """Инициализирует и возвращает клиент Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Переменные окружения SUPABASE_URL и SUPABASE_KEY должны быть установлены.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def load_and_prepare_data() -> list[dict]:
    """Загружает данные из JSON-файлов и подготавливает их к векторизации."""
    prepared_data = []
    
    try:
        with open('data/faq.json', 'r', encoding='utf-8') as f:
            faq_data = json.load(f)
        for item in faq_data:
            content = f"Вопрос: {item['question']}\nОтвет: {item['answer']}"
            prepared_data.append({
                "content": content,
                "source": "FAQ"
            })
        logger.info(f"Загружено {len(faq_data)} записей из FAQ.")
    except FileNotFoundError:
        logger.warning("Файл faq.json не найден, пропущен.")

    try:
        with open('data/interviews.json', 'r', encoding='utf-8') as f:
            interviews_data = json.load(f)
        for item in interviews_data:
            content = item['quote']
            source = f"Цитата из «{item['source_name']}»"
            prepared_data.append({
                "content": content,
                "source": source
            })
        logger.info(f"Загружено {len(interviews_data)} записей из Интервью.")
    except FileNotFoundError:
        logger.warning("Файл interviews.json не найден, пропущен.")
        
    return prepared_data

def vectorize_and_upload(db_client: Client, data: list[dict], model: SentenceTransformer):
    """Векторизует данные и загружает их в Supabase."""
    if not data:
        logger.warning("Нет данных для векторизации. Загрузка отменена.")
        return

    logger.info("Очистка старой базы знаний в Supabase...")
    db_client.table('knowledge_base').delete().neq('id', 0).execute()

    logger.info(f"Начинается векторизация {len(data)} фрагментов текста...")
    
    contents_to_vectorize = [item['content'] for item in data]
    
    embeddings = model.encode(contents_to_vectorize, show_progress_bar=True)
    
    logger.info("Векторизация завершена. Подготовка данных для загрузки...")
    
    records_to_upload = []
    for i, item in enumerate(data):
        records_to_upload.append({
            'content': item['content'],
            'embedding': embeddings[i].tolist(),
            'source': item['source']
        })
        
    logger.info(f"Загрузка {len(records_to_upload)} записей в Supabase...")
    
    db_client.table('knowledge_base').insert(records_to_upload).execute()
    
    logger.info("✅ База знаний успешно векторизована и загружена в Supabase!")

def main():
    """Основная функция скрипта."""
    logger.info("--- Запуск скрипта векторизации базы знаний ---")
    
    db_client = get_db_client()
    logger.info(f"Загрузка модели эмбеддингов: {EMBEDDING_MODEL_NAME}...")
    # --- ИЗМЕНЕНИЕ ЗДЕСЯ ---
    model = SentenceTransformer(EMBEDDING_MODEL_NAME, device='cpu', cache_folder=CACHE_DIR) 
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---
    logger.info("Модель успешно загружена.")

    prepared_data = load_and_prepare_data()

    vectorize_and_upload(db_client, prepared_data, model)
    
    logger.info("--- Скрипт завершил работу ---")


if __name__ == "__main__":
    main()