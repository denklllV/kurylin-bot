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

    def get_active_clients(self) -> List[Dict[str, Any]]:
        try:
            select_query = 'id, client_name, bot_token, manager_contact, quiz_data'
            response = self.client.table('clients').select(select_query).eq('status', 'active').execute()
            logger.info(f"Loaded {len(response.data)} active client(s).")
            return response.data
        except Exception as e:
            logger.error(f"FATAL: Could not load clients from Supabase. Error: {e}", exc_info=True)
            return []

    def get_client_bot_token(self, client_id: int) -> str | None:
        try:
            response = self.client.table('clients').select('bot_token').eq('id', client_id).single().execute()
            if response.data:
                return response.data.get('bot_token')
            return None
        except Exception as e:
            logger.error(f"Error fetching bot token for client {client_id}: {e}")
            return None

    def get_lead_user_ids_by_client(self, client_id: int) -> List[int]:
        try:
            response = self.client.table('leads').select('user_id', count='exact').eq('client_id', client_id).execute()
            user_ids = list(set(item['user_id'] for item in response.data))
            logger.info(f"Found {len(user_ids)} unique lead user(s) for client {client_id}.")
            return user_ids
        except Exception as e:
            logger.error(f"Error fetching lead user IDs for client {client_id}: {e}", exc_info=True)
            return []

    def get_client_system_prompt(self, client_id: int) -> str | None:
        try:
            response = self.client.table('clients').select('system_prompt').eq('id', client_id).single().execute()
            if response.data and response.data.get('system_prompt'):
                return response.data['system_prompt']
            logger.warning(f"System prompt not found or is empty for client {client_id}.")
            return None
        except Exception as e:
            logger.error(f"Error fetching system prompt for client {client_id}: {e}", exc_info=True)
            return None

    def update_client_system_prompt(self, client_id: int, new_prompt: str) -> bool:
        try:
            self.client.table('clients').update({'system_prompt': new_prompt}).eq('id', client_id).execute()
            logger.info(f"System prompt for client {client_id} has been updated.")
            return True
        except Exception as e:
            logger.error(f"Error updating system prompt for client {client_id}: {e}", exc_info=True)
            return False

    def save_user(self, user: User, client_id: int):
        try:
            # ИЗМЕНЕНИЕ: on_conflict теперь указывает на колонки, а не на имя ключа. Это надежнее.
            self.client.table('users').upsert({
                'user_id': user.id, 'username': user.username,
                'first_name': user.first_name, 'utm_source': user.utm_source,
                'client_id': client_id
            }, on_conflict='client_id, user_id').execute()
            logger.info(f"User {user.id} for client {client_id} saved/updated in DB.")
        except Exception as e: 
            logger.error(f"Error saving user {user.id} for client {client_id}: {e}", exc_info=True)

    def get_user_category(self, user_id: int, client_id: int) -> str | None:
        try:
            response = self.client.table('users').select('initial_request_category').eq('user_id', user_id).eq('client_id', client_id).single().execute()
            return response.data.get('initial_request_category')
        except Exception as e:
            if "JSON object requested" not in str(e):
                 logger.error(f"Error getting user category for {user_id} (client {client_id}): {e}")
            return None
            
    def get_user_quiz_status(self, user_id: int, client_id: int) -> Tuple[bool, Dict | None]:
        try:
            response = self.client.table('users').select('quiz_completed_at, quiz_results').eq('user_id', user_id).eq('client_id', client_id).single().execute()
            data = response.data
            if data and data.get('quiz_completed_at'):
                return True, json.loads(data.get('quiz_results')) if data.get('quiz_results') else None
        except Exception:
            pass
        return False, None

    def update_user_category(self, user_id: int, category: str, client_id: int):
        try:
            self.client.table('users').update({'initial_request_category': category}).eq('user_id', user_id).eq('client_id', client_id).execute()
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
            response = self.client.table('messages').select('role, content').eq('user_id', user_id).eq('client_id', client_id).order('created_at', desc=True).limit(limit).execute()
            messages = [Message(role=item['role'], content=item['content']) for item in response.data]
            return list(reversed(messages))
        except Exception as e:
            logger.error(f"Error fetching messages for user {user_id} (client {client_id}): {e}", exc_info=True)
            return []
            
    def find_similar_chunks(self, embedding: List[float], client_id: int, match_threshold: float = 0.5, match_count: int = 3) -> List[Dict[str, Any]]:
        try:
            params = {
                'p_query_embedding': embedding,
                'p_match_threshold': match_threshold,
                'p_match_count': match_count,
                'p_client_id': client_id
            }
            response = self.client.rpc('match_documents', params).execute()
            return response.data
        except Exception as e:
            logger.error(f"Error finding similar chunks for client {client_id}: {e}", exc_info=True)
            return []

    def get_analytics_by_source(self, client_id: int) -> List[Dict[str, Any]]:
        try:
            response = self.client.rpc('get_leads_by_source', {'p_client_id': client_id}).execute()
            return response.data
        except Exception as e:
            logger.error(f"Error getting analytics by source for client {client_id}: {e}", exc_info=True)
            return []
            
    def get_analytics_by_region(self, client_id: int) -> List[Dict[str, Any]]:
        try:
            response = self.client.rpc('get_leads_by_region', {'p_client_id': client_id}).execute()
            return response.data
        except Exception as e:
            logger.error(f"Error getting analytics by region for client {client_id}: {e}", exc_info=True)
            return []

    def get_analytics_by_day_of_week(self, client_id: int) -> List[Dict[str, Any]]:
        try:
            response = self.client.rpc('get_leads_by_day_of_week', {'p_client_id': client_id}).execute()
            return response.data
        except Exception as e:
            logger.error(f"Error getting analytics by day of week for client {client_id}: {e}", exc_info=True)
            return []

    def get_analytics_by_category(self, client_id: int) -> List[Dict[str, Any]]:
        try:
            response = self.client.rpc('get_users_by_category', {'p_client_id': client_id}).execute()
            return response.data
        except Exception as e:
            logger.error(f"Error getting analytics by category for client {client_id}: {e}", exc_info=True)
            return []

# END OF FILE: src/infra/clients/supabase_repo.py