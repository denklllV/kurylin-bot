# Этап 1: Используем официальный образ Python как основу
FROM python:3.11-slim

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Обновляем pip до последней версии
RUN pip install --no-cache-dir --upgrade pip

# Копируем сначала файл с зависимостями и устанавливаем их.
# Это позволяет кэшировать этот слой, если зависимости не меняются.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Сначала копируем ВЕСЬ код приложения в рабочую директорию
COPY . .

# --- ФИНАЛЬНАЯ ИСПРАВЛЕННАЯ ЛОГИКА ---
# Явно создаем группу 'appgroup'
RUN groupadd -r appgroup && \
    # Явно создаем пользователя 'appuser' и добавляем его в группу 'appgroup'
    useradd --no-log-init -r -g appgroup appuser

# Меняем владельца всех файлов в /app на нашего нового пользователя и группу
RUN chown -R appuser:appgroup /app

# Наконец, переключаемся на непривилегированного пользователя
USER appuser
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---

# Указываем команду для запуска приложения
CMD ["python", "main.py"]