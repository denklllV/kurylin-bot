# Этап 1: Используем официальный образ Python как основу
FROM python:3.11-slim

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# --- НОВЫЙ БЛОК: УСТАНОВКА СИСТЕМНЫХ ЗАВИСИМОСТЕЙ ---
# Обновляем список пакетов и устанавливаем ffmpeg.
# Флаг -y автоматически отвечает "да" на все запросы.
# && rm -rf /var/lib/apt/lists/* - очистка кэша для уменьшения размера образа.
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
# --- КОНЕЦ НОВОГО БЛОКА ---

# Обновляем pip до последней версии
RUN pip install --no-cache-dir --upgrade pip

# Копируем сначала файл с зависимостями и устанавливаем их.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Сначала копируем ВЕСЬ код приложения в рабочую директорию
COPY . .

# Явно создаем группу 'appgroup' и пользователя 'appuser'
RUN groupadd -r appgroup && \
    useradd --no-log-init -r -g appgroup appuser

# Меняем владельца всех файлов в /app на нашего нового пользователя и группу
RUN chown -R appuser:appgroup /app

# Наконец, переключаемся на непривилегированного пользователя
USER appuser

# Указываем команду для запуска приложения
CMD ["python", "main.py"]