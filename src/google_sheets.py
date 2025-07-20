# src/google_sheets.py
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from .config import logger, SUPABASE_URL, SUPABASE_KEY, GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_JSON
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Настройки Google Sheets ---
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
# CREDS_FILE = 'google_credentials.json' # <-- Эта строка больше не нужна

def get_sheet():
    """Подключается к Google Sheets и возвращает объект таблицы."""
    try:
        # --- НОВЫЙ БЛОК ДЛЯ АУТЕНТИФИКАЦИИ ИЗ ПЕРЕМЕННОЙ ОКРУЖЕНИЯ ---
        if not GOOGLE_CREDENTIALS_JSON:
            logger.error("Критическая ошибка: переменная окружения GOOGLE_CREDENTIALS_JSON не установлена.")
            return None
            
        creds_json = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, SCOPE)
        # ----------------------------------------------------------------
        
        client = gspread.authorize(creds)
        sheet = client.open_by_key(GOOGLE_SHEET_ID)
        return sheet
    except json.JSONDecodeError:
        logger.error("Критическая ошибка: не удалось разобрать JSON из GOOGLE_CREDENTIALS_JSON. Убедитесь, что это корректный JSON в одну строку.")
        return None
    except Exception as e:
        logger.error(f"Ошибка подключения к Google Sheets: {e}")
        return None

def get_leads_for_period(start_date, end_date):
    """Получает лиды из Supabase за указанный период."""
    try:
        end_date_inclusive = end_date + timedelta(days=1)
        response = supabase.table('leads').select('*, users(utm_source)').gte('created_at', start_date.isoformat()).lt('created_at', end_date_inclusive.isoformat()).order('created_at').execute()
        return response.data
    except Exception as e:
        logger.error(f"Ошибка получения лидов из Supabase: {e}")
        return []

def format_sheet(worksheet):
    """Форматирует заголовок таблицы (делает жирным и закрепляет первую строку)."""
    worksheet.format('A1:Z1', {'textFormat': {'bold': True}})
    worksheet.freeze(rows=1)

def export_to_google_sheets(start_date_str=None, end_date_str=None):
    """Главная функция экспорта. Получает данные и записывает их в таблицу."""
    sheet = get_sheet()
    if not sheet:
        return "Ошибка: Не удалось подключиться к Google Таблице. Проверьте ключ и переменные окружения."

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
    
    leads = get_leads_for_period(start_date, end_date)
    
    try:
        worksheet = sheet.worksheet(sheet_name)
        worksheet.clear()
        logger.info(f"Лист '{sheet_name}' найден и очищен.")
    except gspread.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=sheet_name, rows="100", cols="20")
        logger.info(f"Создан новый лист: '{sheet_name}'.")

    headers = ['Дата и время', 'ID пользователя', 'Имя', 'Сумма долга', 'Источник дохода', 'Регион', 'UTM-метка']
    
    if not leads:
        worksheet.append_row(headers)
        format_sheet(worksheet)
        worksheet.append_row(['Нет данных за этот период.'])
        return f"Отчет за период '{sheet_name}' создан. Лидов не найдено."

    rows_to_insert = [headers]
    for lead in leads:
        utm_source = lead.get('users', {}).get('utm_source') if lead.get('users') else 'N/A'
        created_time = datetime.fromisoformat(lead['created_at'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
        rows_to_insert.append([
            created_time,
            lead['user_id'],
            lead['name'],
            lead['debt_amount'],
            lead['income_source'],
            lead['region'],
            utm_source
        ])
    
    worksheet.append_rows(rows_to_insert, value_input_option='USER_ENTERED')
    format_sheet(worksheet)
    
    return f"Отчет за период '{sheet_name}' успешно выгружен. Добавлено {len(leads)} лидов."