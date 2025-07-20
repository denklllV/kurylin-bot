# Этап 1: Используем официальный образ Python как основу
FROM python:3.11-slim

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Обновляем pip
RUN pip install --no-cache-dir --upgrade pip

# Копируем и устанавливаем Python-зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем ВЕСЬ код приложения в контейнер
COPY . .

# --- НОВЫЙ КЛЮЧЕВОЙ БЛОК ---
# Запускаем скрипт скачивания модели. Это произойдет ОДИН РАЗ при сборке.
# Модель сохранится в /app/cache внутри образа.
RUN python scripts/download_model.py
# --- КОНЕЦ НОВОГО БЛОКА ---

# Создаем безопасного пользователя
RUN groupadd -r appgroup && \
    useradd --no-log-init -r -g appgroup appuser

# Передаем ему права на ВСЕ файлы, включая скачанную модель
RUN chown -R appuser:appgroup /app

# Переключаемся на безопасного пользователя
USER appuser

# Указываем команду для запуска приложения.
# Теперь оно найдет модель локально и запустится мгновенно.
CMD ["python", "main.py"]