# Dockerfile
# 1. Берем за основу готовый образ с Python 3.11
FROM python:3.11-slim

# 2. Устанавливаем системную утилиту ffmpeg
RUN apt-get update && apt-get install -y ffmpeg

# 3. Создаем рабочую папку внутри контейнера
WORKDIR /app

# 4. Копируем наш файл с зависимостями
COPY requirements.txt .

# 5. Устанавливаем Python-библиотеки
RUN pip install --no-cache-dir -r requirements.txt

# 6. Копируем все остальные файлы нашего проекта (папки src, data и т.д.)
COPY . .

# 7. Указываем команду, которая будет запущена при старте контейнера
CMD ["python", "main.py"]