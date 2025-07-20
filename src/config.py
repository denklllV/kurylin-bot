# src/config.py
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Ключи и токены ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
MANAGER_CHAT_ID = os.getenv('MANAGER_CHAT_ID')
HUGGINGFACE_API_KEY = os.getenv('HUGGINGFACE_API_KEY')

# --- Настройки деплоя ---
RENDER_SERVICE_NAME = os.getenv('RENDER_SERVICE_NAME')
WEBHOOK_URL = f"https://{RENDER_SERVICE_NAME}.onrender.com/{TELEGRAM_TOKEN}"
PORT = int(os.environ.get('PORT', 8443))

# --- Настройки моделей AI ---
MODEL_NAME = "tngtech/deepseek-r1t2-chimera:free" 
STT_API_URL = "https://api-inference.huggingface.co/models/openai/whisper-large-v3"
# --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2" 
# --- КОНЕЦ ИЗМЕНЕНИЯ ---

# --- Состояния ConversationHandler ---
GET_NAME, GET_DEBT, GET_INCOME, GET_REGION = range(4)

# --- Настройки опционального лид-магнита ---
LEAD_MAGNET_ENABLED = os.getenv('LEAD_MAGNET_ENABLED', 'False').lower() in ('true', '1', 't')
LEAD_MAGNET_FILE_ID = os.getenv('LEAD_MAGNET_FILE_ID')

# --- Настройки Google Sheets ---
GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
GOOGLE_CREDENTIALS_JSON = os.getenv('GOOGLE_CREDENTIALS_JSON')

# --- База знаний ---
KNOWLEDGE_BASE = ""
try:
    with open('data/bankruptcy_law.md', 'r', encoding='utf-8') as f:
        BANKRUPTCY_CONTEXT = f.read()
    with open('data/interviews.md', 'r', encoding='utf-8') as f:
        INTERVIEWS_CONTEXT = f.read()
    KNOWLEDGE_BASE = BANKRUPTCY_CONTEXT + "\n\n" + INTERVIEWS_CONTEXT
    logger.info("База знаний успешно загружена.")
except FileNotFoundError:
    logger.warning("Внимание: Файлы с базой знаний не найдены в папке data/.")