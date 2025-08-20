# START OF FILE: src/infra/clients/sheets_client.py

import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

from src.shared.logger import logger
# ИЗМЕНЕНИЕ: GOOGLE_SHEET_ID больше не нужен глобально
from src.shared.config import GOOGLE_CREDENTIALS_JSON

class GoogleSheetsClient:
    # ИЗМЕНЕНИЕ: Конструктор теперь принимает sheet_id
    def __init__(self, sheet_id: str):
        if not sheet_id:
            raise ValueError("Google Sheet ID is required.")
        self.scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        self.sheet = self._get_sheet(sheet_id)
        logger.info(f"GoogleSheetsClient initialized for sheet_id: ...{sheet_id[-4:]}")

    def _get_sheet(self, sheet_id: str):
        """Подключается к Google Sheets и возвращает объект таблицы."""
        try:
            if not GOOGLE_CREDENTIALS_JSON:
                logger.error("Переменная окружения GOOGLE_CREDENTIALS_JSON не установлена.")
                return None
            
            creds_json = json.loads(GOOGLE_CREDENTIALS_JSON)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, self.scope)
            client = gspread.authorize(creds)
            # ИЗМЕНЕНИЕ: Открываем таблицу по переданному ID
            return client.open_by_key(sheet_id)
        except Exception as e:
            logger.error(f"Error connecting to Google Sheets for sheet_id ...{sheet_id[-4:]}: {e}")
            return None

    def _format_worksheet(self, worksheet):
        """Форматирует заголовок и закрепляет первую строку."""
        worksheet.format('A1:Z1', {'textFormat': {'bold': True}})
        worksheet.freeze(rows=1)

    def export_leads(self, leads_data: list, start_date_str: str = None, end_date_str: str = None) -> str:
        """Главная функция экспорта. Получает данные и записывает их в таблицу."""
        if not self.sheet:
            return "Ошибка: Не удалось подключиться к Google Таблице. Проверьте права доступа и ID таблицы."

        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                sheet_name = f"{start_date.strftime('%d.%m.%Y')}-{end_date.strftime('%d.%m.%Y')}"
            except ValueError:
                return "Ошибка: Неверный формат даты. Используйте ГГГГ-ММ-ДД."
        else:
            today = datetime.today().date()
            start_of_this_week = today - timedelta(days=today.weekday())
            start_date = start_of_this_week - timedelta(days=7)
            end_date = start_date + timedelta(days=6)
            sheet_name = f"Неделя {start_date.strftime('%W')} ({start_date.strftime('%d.%m')}-{end_date.strftime('%d.%m')})"
        
        try:
            worksheet = self.sheet.worksheet(sheet_name)
            worksheet.clear()
            logger.info(f"Worksheet '{sheet_name}' found and cleared.")
        except gspread.WorksheetNotFound:
            worksheet = self.sheet.add_worksheet(title=sheet_name, rows="100", cols="20")
            logger.info(f"Created new worksheet: '{sheet_name}'.")

        headers = ['Дата и время', 'ID пользователя', 'Имя', 'Сумма долга', 'Источник дохода', 'Регион', 'UTM-метка']
        
        if not leads_data:
            worksheet.append_row(headers)
            self._format_worksheet(worksheet)
            worksheet.append_row(['Нет данных за этот период.'])
            return f"Отчет за период '{sheet_name}' создан. Лидов не найдено."

        rows_to_insert = [headers]
        for lead in leads_data:
            # Предполагаем, что RPC-функция будет возвращать created_at и utm_source
            created_time_str = lead.get('created_at', '')
            created_time = datetime.fromisoformat(created_time_str.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S') if created_time_str else 'N/A'
            
            rows_to_insert.append([
                created_time,
                lead.get('user_id', 'N/A'),
                lead.get('name', 'N/A'),
                lead.get('debt_amount', 'N/A'),
                lead.get('income_source', 'N/A'),
                lead.get('region', 'N/A'),
                lead.get('utm_source', 'N/A')
            ])
        
        worksheet.append_rows(rows_to_insert, value_input_option='USER_ENTERED')
        self._format_worksheet(worksheet)
        
        return f"Отчет за период '{sheet_name}' успешно выгружен. Добавлено {len(leads_data)} лидов."

# END OF FILE: src/infra/clients/sheets_client.py