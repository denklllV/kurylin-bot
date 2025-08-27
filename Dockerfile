# START OF FILE: Dockerfile

# Этап 1: Используем официальный образ Python как основу
FROM python:3.11-slim

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Устанавливаем системные зависимости (сохраняем ffmpeg для аудио)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Обновляем pip
RUN pip install --no-cache-dir --upgrade pip

# Копируем и устанавливаем Python-зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем ВЕСЬ код приложения в контейнер
COPY . .

# Создаем безопасного пользователя (сохраняем вашу лучшую практику)
RUN groupadd -r appgroup && \
    useradd --no-log-init -r -g appgroup appuser

# Передаем ему права
RUN chown -R appuser:appgroup /app

# Переключаемся на безопасного пользователя
USER appuser

# ИЗМЕНЕНИЕ: Указываем новую, продакшн-готовую команду для запуска
# Запускаем Gunicorn, который будет управлять Uvicorn.
# Render будет слушать порт, который Gunicorn откроет по умолчанию.
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "main:fastapi_app"]

# END OF FILE: Dockerfile