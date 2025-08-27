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

# ИЗМЕНЕНИЕ: Указываем более явную и надежную команду запуска для Render
# -b 0.0.0.0:${PORT} - явно привязываемся к порту, который предоставляет Render.
# --log-level debug - включаем подробное логирование для Gunicorn.
CMD ["gunicorn", "-c", "./gunicorn_conf.py", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:${PORT}", "--log-level", "debug", "main:fastapi_app"]

# END OF FILE: Dockerfile