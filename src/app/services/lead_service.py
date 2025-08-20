# START OF FILE: src/app/services/lead_service.py

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
from typing import Dict, List
import asyncio
from telegram.ext import ContextTypes

from src.infra.clients.supabase_repo import SupabaseRepo
from src.domain.models import Lead, User
from src.shared.logger import logger

class LeadService:
    def __init__(self, repo: SupabaseRepo, bot: Bot):
        self.repo = repo
        self.bot = bot
        logger.info("LeadService initialized for multi-tenancy.")

    async def save_lead(self, user: User, lead_data: dict, client_id: int, manager_contact: str):
        lead = Lead(
            user_id=user.id, name=lead_data.get('name'), debt_amount=lead_data.get('debt'),
            income_source=lead_data.get('income'), region=lead_data.get('region')
        )
        self.repo.save_lead(lead, client_id)
        # ИЗМЕНЕНИЕ: Передаем правильный bot-инстанс в _notify_manager_on_lead
        await self._notify_manager_on_lead(user, lead, manager_contact, self.bot)

    async def _notify_manager_on_lead(self, user: User, lead: Lead, manager_contact: str, bot: Bot):
        if not manager_contact:
            return
        username = f"@{user.username}" if user.username else f"ID: {user.id}"
        message_text = (
            f"<b>✅ Новая анкета от {username}</b>\n\n<b>Имя:</b> {lead.name}\n"
            f"<b>Сумма долга:</b> {lead.debt_amount}\n<b>Источник дохода:</b> {lead.income_source}\n"
            f"<b>Регион:</b> {lead.region}"
        )
        try:
            await bot.send_message(chat_id=manager_contact, text=message_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Failed to send lead notification to manager {manager_contact}: {e}", exc_info=True)

    async def send_quiz_results_to_manager(self, user: User, answers: Dict, manager_contact: str):
        if not manager_contact:
            return
        username = f"@{user.username}" if user.username else f"ID: {user.id}"
        report_lines = [f"<b>🎯 Результаты квиза от {username}</b>"]
        for question, answer in answers.items():
            report_lines.append(f"\n<b>{question}</b>\n- {answer}")
        message_text = "\n".join(report_lines)
        try:
            await self.bot.send_message(chat_id=manager_contact, text=message_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Failed to send quiz results to manager {manager_contact}: {e}", exc_info=True)

    async def _broadcast_message_task(self, context: ContextTypes.DEFAULT_TYPE):
        job_data = context.job.data
        bot: Bot = job_data['bot']
        client_id: int = job_data['client_id']
        admin_chat_id: int = job_data['admin_chat_id']
        message: str = job_data.get('message')
        media_type: str | None = job_data.get('media_type')
        media_file_id: str | None = job_data.get('media_file_id')

        user_ids = self.repo.get_lead_user_ids_by_client(client_id)
        if not user_ids:
            await bot.send_message(admin_chat_id, "✅ Рассылка завершена. Не найдено ни одного пользователя, оставившего заявку.")
            return

        successful_sends, failed_sends = 0, 0
        for user_id in user_ids:
            try:
                if media_type == 'photo':
                    await bot.send_photo(chat_id=user_id, photo=media_file_id, caption=message, parse_mode=ParseMode.HTML)
                elif media_type == 'document':
                    await bot.send_document(chat_id=user_id, document=media_file_id, caption=message, parse_mode=ParseMode.HTML)
                else:
                    await bot.send_message(chat_id=user_id, text=message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                successful_sends += 1
            except TelegramError as e:
                logger.error(f"Broadcast failed for user {user_id} (client {client_id}). Error: {e}")
                failed_sends += 1
            await asyncio.sleep(0.1)

        summary_report = (
            f"✅ <b>Рассылка завершена</b>\n\n<b>Клиент ID:</b> {client_id}\n"
            f"<b>Успешно отправлено:</b> {successful_sends}\n<b>Не удалось отправить:</b> {failed_sends}"
        )
        await bot.send_message(admin_chat_id, summary_report, parse_mode=ParseMode.HTML)

# END OF FILE: src/app/services/lead_service.py