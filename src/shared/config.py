# START OF FILE: src/shared/config.py

import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
HF_API_KEY = os.getenv('HF_API_KEY')
GOOGLE_CREDENTIALS_JSON = os.getenv('GOOGLE_CREDENTIALS_JSON')

# --- AI Models & APIs ---
LLM_MODEL_NAME = os.getenv('LLM_MODEL_NAME', "tngtech/deepseek-r1t2-chimera:free")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1"
STT_API_URL = "https://api-inference.huggingface.co/models/openai/whisper-large-v3"

# --- Deployment & Runtime ---
RENDER_SERVICE_NAME = os.getenv('RENDER_SERVICE_NAME')
PUBLIC_APP_URL = f"https://{RENDER_SERVICE_NAME}.onrender.com" if RENDER_SERVICE_NAME else "http://localhost"

PORT = int(os.environ.get('PORT', 8443))
RUN_MODE = os.getenv('RUN_MODE', 'WEBHOOK')

# --- Conversation States ---
# Состояния для анкеты
GET_NAME, GET_DEBT, GET_INCOME, GET_REGION = range(4)

# Состояния для мастера рассылок
GET_BROADCAST_MESSAGE, GET_BROADCAST_MEDIA, CONFIRM_BROADCAST = range(4, 7)

# НОВЫЕ СОСТОЯНИЯ: Для управления чек-листом
CHECKLIST_ACTION, CHECKLIST_UPLOAD_FILE = range(7, 9)

# END OF FILE: src/shared/config.py