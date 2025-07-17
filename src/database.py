# src/database.py
from supabase import create_client, Client
from .config import SUPABASE_URL, SUPABASE_KEY, logger

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_user_to_db(user_id: int, username: str, first_name: str, utm_source: str = None):
    """Сохраняет или обновляет информацию о пользователе. UTM-метка записывается только один раз."""
    try:
        # Сначала проверяем, существует ли пользователь
        response, count = supabase.table('users').select('user_id', count='exact').eq('user_id', user_id).execute()

        if count[1] > 0: # Пользователь уже существует
            # Просто обновляем его данные, не трогая UTM
            supabase.table('users').update({
                'username': username,
                'first_name': first_name
            }).eq('user_id', user_id).execute()
            logger.info(f"Пользователь {user_id} обновлен в БД.")
        else: # Новый пользователь
            # Создаем новую запись со всеми данными
            user_data = {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
            }
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

# --- НИЖЕ ДОБАВЛЕНА НОВАЯ ФУНКЦИЯ ---

def get_all_user_ids() -> list:
    """
    НОВАЯ ФУНКЦИЯ для Шага 1.
    Извлекает ID всех пользователей из таблицы 'users'.
    Это нужно для скрипта массовой рассылки.
    """
    try:
        # Делаем простой запрос к таблице 'users' и просим вернуть только колонку 'user_id'
        response = supabase.table('users').select('user_id').execute()
        
        # API Supabase возвращает объект, где сами данные лежат в поле .data
        # Мы проходимся по списку словарей (например, [{'user_id': 123}, {'user_id': 456}])
        # и извлекаем из каждого словаря только значение ID.
        user_ids = [item['user_id'] for item in response.data]
        
        logger.info(f"Найдено {len(user_ids)} пользователей для возможной рассылки.")
        return user_ids
    except Exception as e:
        logger.error(f"Критическая ошибка при получении списка пользователей из Supabase: {e}")
        return [] # Возвращаем пустой список, чтобы в случае ошибки ничего не сломалось