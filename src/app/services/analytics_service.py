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

    def generate_summary_report(self) -> str:
        """Генерирует полный текстовый отчет для маркетолога."""
        logger.info("Generating analytics summary report...")
        
        try:
            # 1. Получаем данные из репозитория
            source_data = self.repo.get_analytics_by_source()
            region_data = self.repo.get_analytics_by_region()
            dow_data = self.repo.get_analytics_by_day_of_week()

            # 2. Считаем общее количество лидов
            total_leads = sum(item.get('lead_count', 0) for item in source_data)

            # 3. Форматируем каждую секцию
            report_parts = [
                f"📊 <b>Аналитический отчет</b>\n\n<b>Всего лидов: {total_leads}</b>\n",
                self._format_data_as_list(source_data, "Источники лидов (UTM):", "source_name", "lead_count"),
                self._format_data_as_list(region_data, "Топ-10 регионов:", "region_name", "lead_count"),
                self._format_data_as_list(dow_data, "Активность по дням недели:", "day_name", "lead_count"),
            ]
            
            logger.info("Analytics report generated successfully.")
            return "\n\n".join(report_parts)
            
        except Exception as e:
            logger.error(f"Failed to generate analytics report: {e}", exc_info=True)
            return "❌ Не удалось сгенерировать отчет. Подробности в логах сервера."

# END OF FILE: src/app/services/analytics_service.py