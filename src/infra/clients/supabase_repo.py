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
        logger.info("SupabaseRepo initialized.")

    # --- Методы для пользователей и лидов ---
    def save_user(self, user: User):
        try:
            self.client.table('users').upsert({
                'user_id': user.id, 'username': user.username,
                'first_name': user.first_name, 'utm_source': user.utm_source
            }, on_conflict='user_id').execute()
            logger.info(f"User {user.id} saved/updated in DB.")
        except Exception as e: logger.error(f"Error saving user {user.id}: {e}")

    def get_user_category(self, user_id: int) -> str | None:
        try:
            response = self.client.table('users').select('initial_request_category') \
                .eq('user_id', user_id).single().execute()
            return response.data.get('initial_request_category')
        except Exception as e:
            if "JSON object requested, but multiple rows returned" not in str(e) and "JSON object requested, but no rows returned" not in str(e):
                 logger.error(f"Error getting user category for {user_id}: {e}")
            return None
            
    # НОВЫЙ МЕТОД: Получает информацию о прохождении квиза
    def get_user_quiz_status(self, user_id: int) -> Tuple[bool, Dict | None]:
        """Проверяет, проходил ли пользователь квиз, и возвращает его результаты."""
        try:
            response = self.client.table('users').select('quiz_completed_at, quiz_results') \
                .eq('user_id', user_id).single().execute()
            
            data = response.data
            if data and data.get('quiz_completed_at'):
                return True, data.get('quiz_results')
        except Exception:
            # Ошибки здесь не критичны (например, пользователя нет), просто считаем, что квиз не пройден
            pass
        return False, None

    def update_user_category(self, user_id: int, category: str):
        try:
            self.client.table('users').update({'initial_request_category': category}) \
                .eq('user_id', user_id).execute()
            logger.info(f"Updated initial request category for user {user_id} to '{category}'.")
        except Exception as e:
            logger.error(f"Error updating user category for {user_id}: {e}")
            
    def save_quiz_results(self, user_id: int, results: Dict):
        """Сохраняет ответы на квиз и ставит отметку о его прохождении."""
        try:
            # Убедимся, что results - это строка JSON
            results_json = json.dumps(results, ensure_ascii=False)
            self.client.table('users').update({
                'quiz_results': results_json,
                'quiz_completed_at': 'now()'
            }).eq('user_id', user_id).execute()
            logger.info(f"Saved quiz results for user {user_id}.")
        except Exception as e:
            logger.error(f"Error saving quiz results for user {user_id}: {e}")

    def save_lead(self, lead: Lead):
        try:
            self.client.table('leads').insert({
                'user_id': lead.user_id, 'name': lead.name, 'debt_amount': lead.debt_amount,
                'income_source': lead.income_source, 'region': lead.region
            }).execute()
            logger.info(f"Lead for user {lead.user_id} saved.")
        except Exception as e: logger.error(f"Error saving lead for {lead.user_id}: {e}")

    # --- Методы для сообщений ---
    def save_message(self, user_id: int, message: Message):
        try:
            self.client.table('messages').insert({
                'user_id': user_id, 'role': message.role, 'content': message.content
            }).execute()
            logger.info(f"Message from '{message.role}' for user {user_id} saved.")
        except Exception as e: logger.error(f"Error saving message for user {user_id}: {e}")

    def get_recent_messages(self, user_id: int, limit: int = 4) -> List[Message]:
        try:
            response = self.client.table('messages').select('role, content') \
                .eq('user_id', user_id).order('created_at', desc=True).limit(limit).execute()
            messages = [Message(role=item['role'], content=item['content']) for item in response.data]
            return list(reversed(messages))
        except Exception as e:
            logger.error(f"Error fetching recent messages for user {user_id}: {e}")
            return []
            
    # --- Методы для Базы Знаний (RAG) ---
    def find_similar_chunks(self, embedding: List[float], match_threshold: float = 0.5, match_count: int = 3) -> List[Dict[str, Any]]:
        if not embedding: return []
        try:
            response = self.client.rpc('match_documents', {
                'query_embedding': embedding, 'match_threshold': match_threshold, 'match_count': match_count
            }).execute()
            logger.info(f"Vector search returned {len(response.data)} chunk(s).")
            return response.data
        except Exception as e:
            logger.error(f"Error during vector search RPC call: {e}")
            return []

    # --- Методы для Аналитики ---
    def get_analytics_by_source(self) -> List[Dict[str, Any]]:
        try:
            response = self.client.rpc('get_leads_by_source').execute()
            return response.data
        except Exception as e:
            logger.error(f"Error calling RPC get_leads_by_source: {e}")
            return []
            
    def get_analytics_by_region(self) -> List[Dict[str, Any]]:
        try:
            response = self.client.rpc('get_leads_by_region').execute()
            return response.data
        except Exception as e:
            logger.error(f"Error calling RPC get_leads_by_region: {e}")
            return []

    def get_analytics_by_day_of_week(self) -> List[Dict[str, Any]]:
        try:
            response = self.client.rpc('get_leads_by_day_of_week').execute()
            return response.data
        except Exception as e:
            logger.error(f"Error calling RPC get_leads_by_day_of_week: {e}")
            return []

    def get_analytics_by_category(self) -> List[Dict[str, Any]]:
        try:
            response = self.client.rpc('get_users_by_category').execute()
            return response.data
        except Exception as e:
            logger.error(f"Error calling RPC get_users_by_category: {e}")
            return []

# END OF FILE: src/infra/clients/supabase_repo.py