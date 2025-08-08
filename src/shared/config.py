# START OF FILE: src/shared/config.py

import os
from dotenv import load_dotenv

# Загружаем .env файл из корня проекта
load_dotenv()

# --- Telegram ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
MANAGER_CHAT_ID = os.getenv('MANAGER_CHAT_ID')

# --- API Keys ---
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
HF_API_KEY = os.getenv('HF_API_KEY')

# --- AI Models & APIs ---
LLM_MODEL_NAME = os.getenv('LLM_MODEL_NAME', "tngtech/deepseek-r1t2-chimera:free")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1"
STT_API_URL = "https://api-inference.huggingface.co/models/openai/whisper-large-v3"

# --- Deployment & Runtime ---
RENDER_SERVICE_NAME = os.getenv('RENDER_SERVICE_NAME')
PUBLIC_APP_URL = f"https://{RENDER_SERVICE_NAME}.onrender.com" if RENDER_SERVICE_NAME else "http://localhost"

# ИСПРАВЛЕНИЕ ЗДЕСЬ: Возвращаем WEBHOOK_URL, который используется в main.py
WEBHOOK_URL = f"{PUBLIC_APP_URL}/{TELEGRAM_TOKEN}"

PORT = int(os.environ.get('PORT', 8443))
RUN_MODE = os.getenv('RUN_MODE', 'WEBHOOK') # WEBHOOK для Render, POLLING для локального теста

# --- Conversation States ---
GET_NAME, GET_DEBT, GET_INCOME, GET_REGION = range(4)

# END OF FILE: src/shared/config.py