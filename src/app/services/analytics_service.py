# START OF FILE: src/app/services/analytics_service.py

from src.infra.clients.supabase_repo import SupabaseRepo
from src.shared.logger import logger

class AnalyticsService:
    def __init__(self, repo: SupabaseRepo):
        self.repo = repo
        logger.info("AnalyticsService initialized.")

    def _format_data_as_list(self, data: list, title: str, name_key: str, count_key: str) -> str:
        """Вспомогательная функция для форматирования списка данных в строку."""
        if not data:
            return f"<b>{title}</b>\n<i>Нет данных</i>"
        
        lines = [f"<b>{title}</b>"]
        for item in data:
            lines.append(f"- {item.get(name_key, 'N/A')}: {item.get(count_key, 0)}")
        return "\n".join(lines)

    # ИЗМЕНЕНИЕ: Метод теперь принимает client_id
    def generate_summary_report(self, client_id: int) -> str:
        """Генерирует полный текстовый отчет для конкретного клиента."""
        logger.info(f"Generating analytics summary report for client_id: {client_id}...")
        
        try:
            # 1. Получаем все необходимые данные из репозитория, передавая client_id
            source_data = self.repo.get_analytics_by_source(client_id)
            region_data = self.repo.get_analytics_by_region(client_id)
            dow_data = self.repo.get_analytics_by_day_of_week(client_id)
            category_data = self.repo.get_analytics_by_category(client_id)

            # 2. Считаем общее количество лидов
            total_leads = sum(item.get('lead_count', 0) for item in source_data)
            
            # 3. Считаем общее количество пользователей
            total_users = sum(item.get('user_count', 0) for item in category_data)

            # 4. Форматируем каждую секцию в отчет
            report_parts = [
                f"📊 <b>Аналитический отчет (Клиент ID: {client_id})</b>\n\n<b>Всего лидов: {total_leads}</b> | <b>Всего пользователей: {total_users}</b>\n",
                self._format_data_as_list(source_data, "Источники лидов (UTM):", "source_name", "lead_count"),
                self._format_data_as_list(category_data, "Классификация запросов (пользователи):", "category_name", "user_count"),
                self._format_data_as_list(region_data, "Топ-10 регионов (лиды):", "region_name", "lead_count"),
                self._format_data_as_list(dow_data, "Активность по дням недели (лиды):", "day_name", "lead_count"),
            ]
            
            logger.info(f"Analytics report for client {client_id} generated successfully.")
            return "\n\n".join(report_parts)
            
        except Exception as e:
            logger.error(f"Failed to generate analytics report for client {client_id}: {e}", exc_info=True)
            return f"❌ Не удалось сгенерировать отчет для клиента ID {client_id}. Подробности в логах сервера."

# END OF FILE: src/app/services/analytics_service.py