# src/database.py
from supabase import create_client, Client
from datetime import datetime
from .config import SUPABASE_URL, SUPABASE_KEY, logger

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_user_to_db(user_id: int, username: str, first_name: str, utm_source: str = None):
    try:
        response = supabase.table('users').select('user_id', count='exact').eq('user_id', user_id).execute()
        if response.count > 0:
            supabase.table('users').update({'username': username, 'first_name': first_name}).eq('user_id', user_id).execute()
            logger.info(f"Пользователь {user_id} обновлен в БД.")
        else:
            user_data = {'user_id': user_id, 'username': username, 'first_name': first_name}
            if utm_source:
                user_data['utm_source'] = utm_source
            supabase.table('users').insert(user_data).execute()
            logger.info(f"Новый пользователь {user_id} (UTM: {utm_source}) сохранен в БД.")
    except Exception as e:
        logger.error(f"Ошибка при сохранении пользователя {user_id} в Supabase: {e}")

def save_lead_to_db(user_id: int, lead_data: dict):
    """Сохраняет данные из анкеты в таблицу leads."""
    try:
        data_to_insert = {
            'user_id': user_id,
            'name': lead_data.get('name'),
            'debt_amount': lead_data.get('debt'),
            'income_source': lead_data.get('income'),
            'region': lead_data.get('region')
        }
        supabase.table('leads').insert(data_to_insert).execute()
        logger.info(f"Анкета для пользователя {user_id} успешно сохранена в БД.")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении анкеты для {user_id} в Supabase: {e}")
        return False

def get_lead_user_ids() -> list:
    try:
        response = supabase.table('leads').select('user_id').execute()
        all_ids = [item['user_id'] for item in response.data]
        unique_ids = list(set(all_ids))
        logger.info(f"Найдено {len(unique_ids)} уникальных пользователей, оставивших заявку.")
        return unique_ids
    except Exception as e:
        logger.error(f"Критическая ошибка при получении списка лидов из Supabase: {e}")
        return []

def find_similar_chunks(embedding: list[float], match_threshold: float = 0.7, match_count: int = 3) -> list[dict]:
    """
    Ищет наиболее релевантные фрагменты текста в базе знаний с помощью векторного поиска.
    """
    if not embedding:
        return []
    try:
        response = supabase.rpc('match_documents', {
            'query_embedding': embedding,
            'match_threshold': match_threshold,
            'match_count': match_count
        }).execute()
        logger.info(f"Векторный поиск вернул {len(response.data)} фрагмент(ов).")
        return response.data
    except Exception as e:
        logger.error(f"Ошибка при выполнении векторного поиска в Supabase: {e}")
        return []