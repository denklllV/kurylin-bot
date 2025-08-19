# START OF FILE: src/infra/clients/supabase_repo.py

from supabase import create_client, Client
from typing import List, Dict, Any, Tuple
import json

from src.shared.logger import logger
from src.shared.config import SUPABASE_URL, SUPABASE_KEY
from src.domain.models import User, Lead, Message

class SupabaseRepo:
    def __init__(self):
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("SupabaseRepo initialized for multi-tenant architecture.")

    # --- Метод загрузки конфигураций клиентов ---
    def get_active_clients(self) -> List[Dict[str, Any]]:
        """Загружает данные всех активных клиентов из базы данных."""
        try:
            response = self.client.table('clients').select('id, client_name, bot_token, manager_contact') \
                .eq('status', 'active').execute()
            logger.info(f"Loaded {len(response.data)} active client(s).")
            return response.data
        except Exception as e:
            logger.error(f"FATAL: Could not load clients from Supabase. Error: {e}", exc_info=True)
            return []

    # --- Методы для пользователей и лидов (адаптированы под client_id) ---
    def save_user(self, user: User, client_id: int):
        try:
            # Уникальность пользователя теперь определяется парой (user_id, client_id)
            # Это значит, один и тот же человек может быть клиентом разных ботов на нашей платформе
            self.client.table('users').upsert({
                'user_id': user.id, 'username': user.username,
                'first_name': user.first_name, 'utm_source': user.utm_source,
                'client_id': client_id
            }, on_conflict='user_id, client_id').execute()
            logger.info(f"User {user.id} for client {client_id} saved/updated in DB.")
        except Exception as e: logger.error(f"Error saving user {user.id} for client {client_id}: {e}", exc_info=True)

    def get_user_category(self, user_id: int, client_id: int) -> str | None:
        try:
            response = self.client.table('users').select('initial_request_category') \
                .eq('user_id', user_id).eq('client_id', client_id).single().execute()
            return response.data.get('initial_request_category')
        except Exception as e:
            if "JSON object requested" not in str(e): # Игнорируем штатную ошибку "не найдено"
                 logger.error(f"Error getting user category for {user_id} (client {client_id}): {e}")
            return None
            
    def get_user_quiz_status(self, user_id: int, client_id: int) -> Tuple[bool, Dict | None]:
        try:
            response = self.client.table('users').select('quiz_completed_at, quiz_results') \
                .eq('user_id', user_id).eq('client_id', client_id).single().execute()
            data = response.data
            if data and data.get('quiz_completed_at'):
                # Результаты квиза хранятся как JSON-строка, парсим их
                return True, json.loads(data.get('quiz_results')) if data.get('quiz_results') else None
        except Exception:
            pass
        return False, None

    def update_user_category(self, user_id: int, category: str, client_id: int):
        try:
            self.client.table('users').update({'initial_request_category': category}) \
                .eq('user_id', user_id).eq('client_id', client_id).execute()
            logger.info(f"Updated category for user {user_id} (client {client_id}) to '{category}'.")
        except Exception as e:
            logger.error(f"Error updating category for user {user_id} (client {client_id}): {e}", exc_info=True)
            
    def save_quiz_results(self, user_id: int, results: Dict, client_id: int):
        try:
            results_json = json.dumps(results, ensure_ascii=False)
            self.client.table('users').update({
                'quiz_results': results_json,
                'quiz_completed_at': 'now()'
            }).eq('user_id', user_id).eq('client_id', client_id).execute()
            logger.info(f"Saved quiz results for user {user_id} (client {client_id}).")
        except Exception as e:
            logger.error(f"Error saving quiz results for user {user_id} (client {client_id}): {e}", exc_info=True)

    def save_lead(self, lead: Lead, client_id: int):
        try:
            self.client.table('leads').insert({
                'user_id': lead.user_id, 'name': lead.name, 'debt_amount': lead.debt_amount,
                'income_source': lead.income_source, 'region': lead.region,
                'client_id': client_id
            }).execute()
            logger.info(f"Lead for user {lead.user_id} (client {client_id}) saved.")
        except Exception as e: logger.error(f"Error saving lead for {lead.user_id} (client {client_id}): {e}", exc_info=True)

    # --- Методы для сообщений (адаптированы под client_id) ---
    def save_message(self, user_id: int, message: Message, client_id: int):
        try:
            self.client.table('messages').insert({
                'user_id': user_id, 'role': message.role, 'content': message.content,
                'client_id': client_id
            }).execute()
            logger.info(f"Message from '{message.role}' for user {user_id} (client {client_id}) saved.")
        except Exception as e: logger.error(f"Error saving message for user {user_id} (client {client_id}): {e}", exc_info=True)

    def get_recent_messages(self, user_id: int, client_id: int, limit: int = 4) -> List[Message]:
        try:
            response = self.client.table('messages').select('role, content') \
                .eq('user_id', user_id).eq('client_id', client_id).order('created_at', desc=True).limit(limit).execute()
            messages = [Message(role=item['role'], content=item['content']) for item in response.data]
            return list(reversed(messages))
        except Exception as e:
            logger.error(f"Error fetching messages for user {user_id} (client {client_id}): {e}", exc_info=True)
            return []
            
    # --- RAG и Аналитика (требуют адаптации RPC-функций в SQL) ---
    # Мы пока не можем их полностью реализовать, пока не обновим SQL-функции.
    # Поэтому пока они будут возвращать пустые списки.
    def find_similar_chunks(self, embedding: List[float], client_id: int, match_threshold: float = 0.5, match_count: int = 3) -> List[Dict[str, Any]]:
        logger.warning("find_similar_chunks is not yet adapted for multi-tenancy RPC.")
        return []

    def get_analytics_by_source(self, client_id: int) -> List[Dict[str, Any]]:
        logger.warning("get_analytics_by_source is not yet adapted for multi-tenancy RPC.")
        return []
            
    def get_analytics_by_region(self, client_id: int) -> List[Dict[str, Any]]:
        logger.warning("get_analytics_by_region is not yet adapted for multi-tenancy RPC.")
        return []

    def get_analytics_by_day_of_week(self, client_id: int) -> List[Dict[str, Any]]:
        logger.warning("get_analytics_by_day_of_week is not yet adapted for multi-tenancy RPC.")
        return []

    def get_analytics_by_category(self, client_id: int) -> List[Dict[str, Any]]:
        logger.warning("get_analytics_by_category is not yet adapted for multi-tenancy RPC.")
        return []

# END OF FILE: src/infra/clients/supabase_repo.py