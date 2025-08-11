# START OF FILE: src/app/services/lead_service.py

from telegram import Bot
from telegram.constants import ParseMode

from src.infra.clients.supabase_repo import SupabaseRepo
from src.domain.models import Lead, User
from src.shared.logger import logger
from src.shared.config import MANAGER_CHAT_ID

class LeadService:
    def __init__(self, repo: SupabaseRepo, bot: Bot):
        self.repo = repo
        self.bot = bot
        logger.info("LeadService initialized.")

    # ИЗМЕНЕНИЕ: Делаем метод асинхронным, чтобы он мог вызывать другие асинхронные методы
    async def save_lead(self, user: User, lead_data: dict):
        lead = Lead(
            user_id=user.id,
            name=lead_data.get('name'),
            debt_amount=lead_data.get('debt'),
            income_source=lead_data.get('income'),
            region=lead_data.get('region')
        )
        self.repo.save_lead(lead)
        # ИЗМЕНЕНИЕ: Используем await для вызова асинхронного метода
        await self._notify_manager(user, lead)

    async def _notify_manager(self, user: User, lead: Lead):
        if not MANAGER_CHAT_ID:
            logger.warning("MANAGER_CHAT_ID is not set. Skipping notification.")
            return

        username = f"@{user.username}" if user.username else f"ID: {user.id}"
        message_text = (
            f"<b>✅ Новая анкета от {username}</b>\n\n"
            f"<b>Имя:</b> {lead.name}\n"
            f"<b>Сумма долга:</b> {lead.debt_amount}\n"
            f"<b>Источник дохода:</b> {lead.income_source}\n"
            f"<b>Регион:</b> {lead.region}"
        )
        try:
            await self.bot.send_message(
                chat_id=MANAGER_CHAT_ID,
                text=message_text,
                parse_mode=ParseMode.HTML
            )
            logger.info(f"Notification for new lead from {user.id} sent to manager.")
        except Exception as e:
            logger.error(f"Failed to send lead notification to manager: {e}")

# END OF FILE: src/app/services/lead_service.py