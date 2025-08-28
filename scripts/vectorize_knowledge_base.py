# path: scripts/vectorize_knowledge_base.py
import argparse
import json
import os
import sys
from pathlib import Path

# --- НАДЁЖНЫЙ ШАБЛОН ЗАГРУЗКИ ---
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
from dotenv import load_dotenv
load_dotenv(project_root / ".env")
# ------------------------------------

from sentence_transformers import SentenceTransformer
from src.infra.clients.supabase_repo import SupabaseRepo
from src.shared.logger import logger

def load_data_from_file(file_path: str) -> list[dict]:
    """Загружает и подготавливает данные из файла (пока только .json)."""
    prepared_data = []
    
    if not os.path.exists(file_path):
        logger.error(f"Файл не найден по пути: {file_path}")
        return prepared_data

    if file_path.endswith('.json'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                faq_data = json.load(f)
            
            # Валидация структуры
            if not isinstance(faq_data, list) or not all(isinstance(item, dict) for item in faq_data):
                 raise ValueError("JSON должен быть списком объектов.")

            for item in faq_data:
                question = item.get('question')
                answer = item.get('answer')
                if not question or not answer:
                    logger.warning(f"Пропущена запись из-за отсутствия 'question' или 'answer': {item}")
                    continue
                
                content = f"Вопрос: {question}\nОтвет: {answer}"
                prepared_data.append({"content": content, "source": os.path.basename(file_path)})
            logger.info(f"Успешно загружено {len(prepared_data)} записей из {file_path}.")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Ошибка чтения или валидации JSON файла {file_path}: {e}")
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при обработке {file_path}: {e}", exc_info=True)
    else:
        logger.error(f"Формат файла не поддерживается: {file_path}. Поддерживается только .json.")

    return prepared_data


def run_vectorization(client_id: int, file_path: str, clear_before_upload: bool):
    """
    Вычисляет эмбеддинги для данных из файла и загружает их в Supabase
    для конкретного client_id.
    """
    logger.info(f"--- Запуск векторизации для клиента ID: {client_id} ---")
    
    data_to_process = load_data_from_file(file_path)
    if not data_to_process:
        logger.warning("Нет данных для обработки. Завершение работы."); return

    model_name = 'cointegrated/rubert-tiny2'
    logger.info(f"Загрузка локальной модели SentenceTransformer: {model_name}...")
    try:
        model = SentenceTransformer(model_name, device='cpu')
    except Exception as e:
        logger.error(f"Не удалось загрузить модель: {e}", exc_info=True); return
        
    contents = [item['content'] for item in data_to_process]
    logger.info(f"Кодирование {len(contents)} документов...")
    embeddings = model.encode(contents, show_progress_bar=True)
    
    records_to_upload = [
        {
            'content': item['content'], 
            'embedding': emb.tolist(), 
            'source': item['source'],
            'client_id': client_id  # <-- КЛЮЧЕВОЕ ИЗМЕНЕНИЕ
        }
        for item, emb in zip(data_to_process, embeddings)
    ]
    
    repo = SupabaseRepo()

    if clear_before_upload:
        logger.warning(f"Опция --clear включена. Удаление ВСЕХ предыдущих записей из базы знаний для клиента {client_id}...")
        repo.clear_knowledge_base_for_client(client_id)
        logger.info(f"База знаний для клиента {client_id} очищена.")

    logger.info(f"Загрузка {len(records_to_upload)} записей в Supabase...")
    repo.insert_into_knowledge_base(records_to_upload)
    
    logger.info(f"✅ База знаний для клиента {client_id} успешно векторизована и загружена!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Скрипт для векторизации и загрузки базы знаний для конкретного клиента.")
    parser.add_argument("--client-id", type=int, required=True, help="ID клиента, для которого загружается база знаний.")
    parser.add_argument("--file-path", type=str, required=True, help="Путь к .json файлу с данными (список объектов с ключами 'question' и 'answer').")
    parser.add_argument("--clear", action="store_true", help="Если указано, полностью очистить базу знаний для этого клиента перед загрузкой новых данных.")
    args = parser.parse_args()
    
    run_vectorization(args.client_id, args.file_path, args.clear)
# path: scripts/vectorize_knowledge_base.py