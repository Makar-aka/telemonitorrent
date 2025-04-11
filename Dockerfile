# Используем официальный образ Python
FROM python:3.9-slim

RUN groupadd -g 1000 appgroup && \
    useradd -m -u 1000 -g appgroup appuser

RUN ../touch bot.log && \
    chown -R appuser:appgroup .

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта
COPY . /app

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Указываем переменные окружения
ENV PYTHONUNBUFFERED=1


# Команда для запуска приложения
CMD ["python", "bot.py"]
