# START OF FILE: Dockerfile

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

# Создаем безопасного пользователя
RUN groupadd -r appgroup && \
    useradd --no-log-init -r -g appgroup appuser

# Передаем ему права
RUN chown -R appuser:appgroup /app

# Переключаемся на безопасного пользователя
USER appuser

# ИЗМЕНЕНИЕ: Указываем Gunicorn использовать наш конфигурационный файл.
# Все параметры (workers, bind, port) теперь находятся внутри gunicorn_conf.py
CMD ["gunicorn", "-c", "./gunicorn_conf.py", "main:fastapi_app"]

# END OF FILE: Dockerfile