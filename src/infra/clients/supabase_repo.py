# START OF FILE: src/infra/clients/supabase_repo.py

from supabase import create_client, Client
from typing import List, Dict, Any

from src.shared.logger import logger
from src.shared.config import SUPABASE_URL, SUPABASE_KEY
# ИСПРАВЛЕНИЕ: Используем точки вместо слэшей для импорта
from src.domain.models import User, Lead, Message

class SupabaseRepo:
    def __init__(self):
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("SupabaseRepo initialized.")

    # --- Методы для пользователей и лидов (без изменений) ---
    def save_user(self, user: User):
        try:
            self.client.table('users').upsert({
                'user_id': user.id, 'username': user.username,
                'first_name': user.first_name, 'utm_source': user.utm_source
            }, on_conflict='user_id').execute()
            logger.info(f"User {user.id} saved/updated in DB.")
        except Exception as e: logger.error(f"Error saving user {user.id}: {e}")

    def save_lead(self, lead: Lead):
        try:
            self.client.table('leads').insert({
                'user_id': lead.user_id, 'name': lead.name, 'debt_amount': lead.debt_amount,
                'income_source': lead.income_source, 'region': lead.region
            }).execute()
            logger.info(f"Lead for user {lead.user_id} saved.")
        except Exception as e: logger.error(f"Error saving lead for {lead.user_id}: {e}")

    # --- Методы для сообщений (без изменений) ---
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
            # ИЗМЕНЕНИЕ: Добавляем метод to_dict() для сериализации
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

    # --- Методы для переиндексации (без изменений) ---
    def get_all_knowledge_chunks(self) -> List[Dict[str, Any]]:
        """Получает все записи из базы знаний для переиндексации."""
        try:
            response = self.client.table('knowledge_base').select('id, content').execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to fetch all knowledge chunks: {e}")
            return []

    def update_chunk_embedding(self, chunk_id: int, embedding: List[float]):
        """Обновляет эмбеддинг для конкретного чанка."""
        try:
            self.client.table('knowledge_base').update({'embedding': embedding}).eq('id', chunk_id).execute()
            logger.info(f"Successfully updated embedding for chunk ID {chunk_id}.")
        except Exception as e:
            logger.error(f"Failed to update embedding for chunk ID {chunk_id}: {e}")

# END OF FILE: src/infra/clients/supabase_repo.py