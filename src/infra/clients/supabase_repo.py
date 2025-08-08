# START OF FILE: src/infra/clients/supabase_repo.py

from supabase import create_client, Client
from typing import List

from src.shared.logger import logger
from src.shared.config import SUPABASE_URL, SUPABASE_KEY
from src.domain.models import User, Lead, Message

class SupabaseRepo:
    def __init__(self):
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized.")

    def save_user(self, user: User):
        try:
            # Upsert logic: insert or update if user exists
            self.client.table('users').upsert({
                'user_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'utm_source': user.utm_source
            }, on_conflict='user_id').execute()
            logger.info(f"User {user.id} saved/updated in DB.")
        except Exception as e:
            logger.error(f"Error saving user {user.id} to Supabase: {e}")

    def save_lead(self, lead: Lead):
        try:
            self.client.table('leads').insert({
                'user_id': lead.user_id,
                'name': lead.name,
                'debt_amount': lead.debt_amount,
                'income_source': lead.income_source,
                'region': lead.region
            }).execute()
            logger.info(f"Lead for user {lead.user_id} saved.")
        except Exception as e:
            logger.error(f"Error saving lead for {lead.user_id}: {e}")

    def save_message(self, user_id: int, message: Message):
        try:
            self.client.table('messages').insert({
                'user_id': user_id,
                'role': message.role,
                'content': message.content
            }).execute()
            logger.info(f"Message from '{message.role}' for user {user_id} saved.")
        except Exception as e:
            logger.error(f"Error saving message for user {user_id}: {e}")

# END OF FILE: src/infra/clients/supabase_repo.py