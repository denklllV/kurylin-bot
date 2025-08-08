# START OF FILE: src/infra/clients/hf_whisper_client.py

import requests

from src.shared.logger import logger
from src.shared.config import HF_API_KEY, STT_API_URL

class WhisperClient:
    def __init__(self):
        self.api_url = STT_API_URL
        self.headers = {"Authorization": f"Bearer {HF_API_KEY}"}
        logger.info("WhisperClient initialized.")

    def transcribe(self, audio_data: bytes) -> str | None:
        try:
            logger.info("Sending audio data for transcription...")
            response = requests.post(self.api_url, headers=self.headers, data=audio_data)
            response.raise_for_status()

            # ИСПРАВЛЕНИЕ: Проверяем, что ответ является JSON, перед парсингом
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
                # Если пришел не JSON (например, HTML), логируем это
                logger.error(f"Transcription API returned a non-JSON response. Content-Type: {content_type}.")
                return None

        except Exception as e:
            logger.error(f"Error during transcription request: {e}")
            return None

# END OF FILE: src/infra/clients/hf_whisper_client.py