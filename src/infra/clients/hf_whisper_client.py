# START OF FILE: src/infra/clients/hf_whisper_client.py

import requests

from src.shared.logger import logger
from src.shared.config import HF_API_KEY, STT_API_URL

class WhisperClient:
    def __init__(self):
        self.api_url = STT_API_URL
        
        # --- ИЗМЕНЕНИЕ ЗДЕСЬ: Добавляем диагностику ключа ---
        if HF_API_KEY and len(HF_API_KEY) > 10:
            # Логируем, что ключ получен, его тип и длину, но не сам ключ
            logger.info(f"DIAGNOSTICS: HF_API_KEY loaded. Type: {type(HF_API_KEY)}, Length: {len(HF_API_KEY)}.")
        else:
            # Если ключ пустой или слишком короткий, бьем тревогу
            logger.error("DIAGNOSTICS: HF_API_KEY is missing, empty, or invalid!")

        self.headers = {
            "Authorization": f"Bearer {HF_API_KEY}",
            "Accept": "application/json",
            "Content-Type": "audio/mp3"
        }
        logger.info("WhisperClient initialized with explicit headers.")

    def transcribe(self, audio_data: bytes) -> str | None:
        try:
            logger.info(f"Sending {len(audio_data)} bytes of audio data for transcription...")
            response = requests.post(self.api_url, headers=self.headers, data=audio_data)
            response.raise_for_status()

            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                response_data = response.json()
                transcribed_text = response_data.get('text')
                
                if transcribed_text:
                    logger.info(f"Transcription successful: '{transcribed_text}'")
                    return transcribed_text.strip()
                else:
                    logger.warning(f"Transcription API returned JSON but no text. Response: {response_data}")
                    return None
            else:
                logger.error(f"Transcription API returned a non-JSON response. Content-Type: {content_type}.")
                return None

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error during transcription request: {e}. Response body: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Generic error during transcription request: {e}")
            return None

# END OF FILE: src/infra/clients/hf_whisper_client.py