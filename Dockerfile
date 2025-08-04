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

# --- УДАЛЯЕМ НЕНУЖНЫЙ БЛОК ---
# RUN python scripts/download_model.py # <-- ЭТА СТРОКА БОЛЬШЕ НЕ НУЖНА
# --- КОНЕЦ УДАЛЕНИЯ ---

# Создаем безопасного пользователя
RUN groupadd -r appgroup && \
    useradd --no-log-init -r -g appgroup appuser

# Передаем ему права
RUN chown -R appuser:appgroup /app

# Переключаемся на безопасного пользователя
USER appuser

# Указываем команду для запуска приложения
CMD ["python", "main.py"]