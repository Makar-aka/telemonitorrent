# Используем официальный образ Python
FROM python:3.9-slim

# Создаём группу и пользователя
RUN groupadd -g 1000 appgroup && \
    useradd -m -u 1000 -g appgroup appuser

# Устанавливаем рабочую директорию
WORKDIR /app

# Создаём директорию files с правильными правами
RUN mkdir -p /app/files && \
    chown -R appuser:appgroup /app/files



# Копируем файлы проекта
COPY . /app

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Переключаемся на пользователя appuser
USER appuser

# Указываем переменные окружения
ENV PYTHONUNBUFFERED=1

# Команда для запуска приложения
CMD ["python", "bot.py"]
