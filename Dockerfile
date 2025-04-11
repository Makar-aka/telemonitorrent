# Используем официальный образ Python
FROM python:3.9-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта
COPY . /app

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Указываем переменные окружения
ENV PYTHONUNBUFFERED=1

# Открываем порт (если требуется)
EXPOSE 8080

# Команда для запуска приложения
CMD ["python", "bot.py"]
