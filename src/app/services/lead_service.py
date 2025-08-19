# START OF FILE: src/app/services/lead_service.py

from telegram import Bot
from telegram.constants import ParseMode
from typing import Dict

from src.infra.clients.supabase_repo import SupabaseRepo
from src.domain.models import Lead, User
from src.shared.logger import logger

class LeadService:
    def __init__(self, repo: SupabaseRepo, bot: Bot):
        self.repo = repo
        self.bot = bot
        logger.info("LeadService initialized for multi-tenancy.")

    async def save_lead(self, user: User, lead_data: dict, client_id: int, manager_contact: str):
        """Сохраняет лид и уведомляет менеджера конкретного клиента."""
        lead = Lead(
            user_id=user.id,
            name=lead_data.get('name'),
            debt_amount=lead_data.get('debt'),
            income_source=lead_data.get('income'),
            region=lead_data.get('region')
        )
        self.repo.save_lead(lead, client_id)
        await self._notify_manager_on_lead(user, lead, manager_contact)

    async def _notify_manager_on_lead(self, user: User, lead: Lead, manager_contact: str):
        """Внутренний метод для отправки уведомления о новой анкете."""
        if not manager_contact:
            logger.warning("Manager contact is not set for this client. Skipping notification.")
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
                chat_id=manager_contact, text=message_text, parse_mode=ParseMode.HTML
            )
            logger.info(f"Notification for new lead from {user.id} sent to manager {manager_contact}.")
        except Exception as e:
            logger.error(f"Failed to send lead notification to manager {manager_contact}: {e}", exc_info=True)

    async def send_quiz_results_to_manager(self, user: User, answers: Dict, manager_contact: str):
        """Форматирует и отправляет результаты квиза менеджеру конкретного клиента."""
        if not manager_contact:
            logger.warning("Manager contact is not set for this client. Skipping quiz results notification.")
            return

        username = f"@{user.username}" if user.username else f"ID: {user.id}"
        
        report_lines = [f"<b>🎯 Результаты квиза от {username}</b>"]
        for question, answer in answers.items():
            report_lines.append(f"\n<b>{question}</b>\n- {answer}")
        message_text = "\n".join(report_lines)
        
        try:
            await self.bot.send_message(
                chat_id=manager_contact, text=message_text, parse_mode=ParseMode.HTML
            )
            logger.info(f"Quiz results for user {user.id} sent to manager {manager_contact}.")
        except Exception as e:
            logger.error(f"Failed to send quiz results to manager {manager_contact}: {e}", exc_info=True)

# END OF FILE: src/app/services/lead_service.py