# START OF FILE: src/infra/clients/supabase_repo.py

from supabase import create_client, Client
from typing import List, Dict, Any

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

    # НОВЫЙ МЕТОД: Проверяет наличие категории у пользователя
    def get_user_category(self, user_id: int) -> str | None:
        """Получает категорию первого запроса пользователя. Возвращает None, если ее нет."""
        try:
            response = self.client.table('users').select('initial_request_category') \
                .eq('user_id', user_id).single().execute()
            return response.data.get('initial_request_category')
        except Exception as e:
            # PostgrestError может возникнуть, если пользователя еще нет, это не ошибка
            if "JSON object requested, but multiple rows returned" not in str(e) and "JSON object requested, but no rows returned" not in str(e):
                 logger.error(f"Error getting user category for {user_id}: {e}")
            return None # В любом случае считаем, что категории нет

    # НОВЫЙ МЕТОД: Обновляет категорию пользователя
    def update_user_category(self, user_id: int, category: str):
        """Обновляет категорию первого запроса для пользователя."""
        try:
            self.client.table('users').update({'initial_request_category': category}) \
                .eq('user_id', user_id).execute()
            logger.info(f"Updated initial request category for user {user_id} to '{category}'.")
        except Exception as e:
            logger.error(f"Error updating user category for {user_id}: {e}")

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
        # Этот метод пока не работает из-за проблем с эмбеддингами, но мы его оставляем
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
        """Получает статистику лидов по UTM-меткам, вызывая RPC."""
        try:
            response = self.client.rpc('get_leads_by_source').execute()
            return response.data
        except Exception as e:
            logger.error(f"Error calling RPC get_leads_by_source: {e}")
            return []
            
    def get_analytics_by_region(self) -> List[Dict[str, Any]]:
        """Получает статистику лидов по регионам, вызывая RPC."""
        try:
            response = self.client.rpc('get_leads_by_region').execute()
            return response.data
        except Exception as e:
            logger.error(f"Error calling RPC get_leads_by_region: {e}")
            return []

    def get_analytics_by_day_of_week(self) -> List[Dict[str, Any]]:
        """Получает статистику лидов по дням недели, вызывая RPC."""
        try:
            response = self.client.rpc('get_leads_by_day_of_week').execute()
            return response.data
        except Exception as e:
            logger.error(f"Error calling RPC get_leads_by_day_of_week: {e}")
            return []

# END OF FILE: src/infra/clients/supabase_repo.py