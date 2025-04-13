# Используем официальный образ Python
FROM python:3.9-slim

# Создаём группу и пользователя для безопасного выполнения
RUN groupadd -g 1000 appgroup && \
    useradd -m -u 1000 -g appgroup appuser

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта в контейнер
COPY . /app

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Создаём необходимые файлы и директории с правильными правами
RUN mkdir -p /app/files && \
    touch /app/database.db /app/users.db /app/bot.log && \
    chmod 666 /app/database.db /app/users.db /app/bot.log && \
    chown -R appuser:appgroup /app

# Переключаемся на пользователя appuser
USER appuser

# Указываем переменные окружения
ENV PYTHONUNBUFFERED=1

# Команда для запуска приложения
CMD ["python", "bot.py"]
