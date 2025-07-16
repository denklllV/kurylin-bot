# src/config.py
import os
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env, который должен быть в корневой папке
load_dotenv()

# Настройка логирования для всего проекта
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Ключи и токены из .env ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
MANAGER_CHAT_ID = os.getenv('MANAGER_CHAT_ID')

# --- Настройки для деплоя на Render ---
RENDER_SERVICE_NAME = os.getenv('RENDER_SERVICE_NAME')
WEBHOOK_URL = f"https://{RENDER_SERVICE_NAME}.onrender.com/{TELEGRAM_TOKEN}"
PORT = int(os.environ.get('PORT', 8443))

# --- Настройки моделей и AI ---
# ИСПРАВЛЕННОЕ ИМЯ МОДЕЛИ (без моей опечатки)
MODEL_NAME = "tngtech/deepseek-r1t2-chimera:free" 

# --- Состояния для ConversationHandler ---
GET_NAME, GET_DEBT, GET_INCOME, GET_REGION = range(4)

# --- Загрузка базы знаний ---
KNOWLEDGE_BASE = ""
try:
    # Важно: теперь мы указываем правильный путь к папке data/
    with open('data/bankruptcy_law.md', 'r', encoding='utf-8') as f:
        BANKRUPTCY_CONTEXT = f.read()
    with open('data/interviews.md', 'r', encoding='utf-8') as f:
        INTERVIEWS_CONTEXT = f.read()
    KNOWLEDGE_BASE = BANKRUPTCY_CONTEXT + "\n\n" + INTERVIEWS_CONTEXT
    logger.info("База знаний успешно загружена.")
except FileNotFoundError:
    logger.warning("Внимание: Файлы с базой знаний не найдены в папке data/. Убедитесь, что они там.")