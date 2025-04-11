# ���������� ����������� ����� Python
FROM python:3.9-slim

# ������ ������ � ������������
RUN groupadd -g 1000 appgroup && \
    useradd -m -u 1000 -g appgroup appuser

# ������������� ������� ����������
WORKDIR /app

# ������ ���������� files � ����������� �������
RUN mkdir -p /app/files && \
    chown -R appuser:appgroup /app/files

RUN touch /app/database.db /app/users.db && \
    chmod 666 /app/database.db /app/users.db && \
    chown appuser:appgroup /app/database.db /app/users.db

# �������� ����� �������
COPY . /app

# ������������� �����������
RUN pip install --no-cache-dir -r requirements.txt

# ������������� �� ������������ appuser
USER appuser

# ��������� ���������� ���������
ENV PYTHONUNBUFFERED=1

# ������� ��� ������� ����������
CMD ["python", "bot.py"]
