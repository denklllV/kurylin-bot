# scripts/send_broadcast.py
import argparse
import asyncio
import os
import sys

# Добавляем корневую директорию проекта в sys.path для импорта модулей из src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла в самом начале
load_dotenv()

# Теперь, когда переменные загружены, можно импортировать наши модули
from src.config import TELEGRAM_TOKEN, logger
from src.database import get_lead_user_ids # <-- ИСПОЛЬЗУЕМ НОВУЮ ФУНКЦИЮ

async def broadcast(bot: Bot, message: str, dry_run: bool):
    """
    Основная функция для выполнения рассылки.
    """
    # Шаг 1: Получаем список ID только тех, кто оставил заявку
    user_ids = get_lead_user_ids()
    if not user_ids:
        logger.info("В базе данных нет пользователей, оставивших заявку. Рассылка отменена.")
        return

    logger.info(f"Начинаем рассылку для {len(user_ids)} пользователей...")
    if dry_run:
        logger.warning("--- РЕЖИМ ТЕСТОВОГО ЗАПУСКА (DRY-RUN) ---")
        logger.warning("Сообщения не будут отправлены, только показан список ID и текст.")
        logger.warning(f"Целевые ID: {user_ids}")
        logger.warning(f"Текст сообщения: «{message}»")
        logger.warning("---------------------------------------")
        return

    # Шаг 2: Последовательно отправляем сообщения с мерами предосторожности
    successful_sends = 0
    failed_sends = 0

    for user_id in user_ids:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True # Отключаем превью ссылок для более компактного вида
            )
            logger.info(f"Сообщение успешно отправлено пользователю {user_id}")
            successful_sends += 1
        except TelegramError as e:
            # Самая частая ошибка - пользователь заблокировал бота.
            # Мы должны обработать это, чтобы скрипт не "упал", а продолжил работу.
            logger.error(f"Не удалось отправить сообщение пользователю {user_id}. Ошибка: {e}")
            failed_sends += 1
        
        # МЕРА БЕЗОПАСНОСТИ №1: Пауза между отправками.
        # Telegram разрешает до 30 сообщений в секунду. Мы делаем с запасом: 10 сообщений в секунду.
        # Этого более чем достаточно для защиты от блокировок.
        await asyncio.sleep(0.1)

    logger.info("----- РЕЗУЛЬТАТЫ РАССЫЛКИ -----")
    logger.info(f"✅ Успешно отправлено: {successful_sends}")
    logger.info(f"❌ Не удалось отправить: {failed_sends}")
    logger.info("-------------------------------")

async def main():
    # МЕРА БЕЗОПАСНОСТИ №2: Удобный интерфейс командной строки.
    # Это позволяет избежать случайных запусков.
    # --dry-run позволяет проверить, что всё работает, без реальной отправки.
    parser = argparse.ArgumentParser(description="Скрипт для рассылки сообщений пользователям, оставившим заявку.")
    parser.add_argument("message", type=str, help="Текст сообщения в кавычках. Можно использовать HTML-теги: <b>, <i>, <a>.")
    parser.add_argument("--dry-run", action="store_true", help="Запустить в тестовом режиме без реальной отправки сообщений.")
    args = parser.parse_args()

    if not TELEGRAM_TOKEN:
        logger.error("Токен TELEGRAM_TOKEN не найден. Убедитесь, что в корне проекта есть .env файл.")
        return

    bot = Bot(token=TELEGRAM_TOKEN)
    await broadcast(bot, args.message, args.dry_run)

if __name__ == "__main__":
    asyncio.run(main())