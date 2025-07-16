# src/database.py
from supabase import create_client, Client

# Импортируем нужные переменные и логгер из нашего конфига
from .config import SUPABASE_URL, SUPABASE_KEY, logger

# Создаем клиент Supabase один раз при запуске модуля
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_user_to_db(user_id: int, username: str, first_name: str):
    """Сохраняет или обновляет информацию о пользователе в таблице users."""
    try:
        # Метод upsert удобно обновляет запись, если она есть, или создает новую
        supabase.table('users').upsert({
            'user_id': user_id,
            'username': username,
            'first_name': first_name
        }).execute()
        logger.info(f"Пользователь {user_id} сохранен или обновлен в БД.")
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
        return True # Возвращаем True в случае успеха
    except Exception as e:
        logger.error(f"Ошибка при сохранении анкеты для {user_id} в Supabase: {e}")
        return False # Возвращаем False в случае ошибки