# ���������� ����������� ����� Python
FROM python:3.9-slim

# ������ ������ � ������������ ��� ����������� ����������
RUN groupadd -g 1000 appgroup && \
    useradd -m -u 1000 -g appgroup appuser

# ������������� ������� ����������
WORKDIR /app

# �������� ����� ������� � ���������
COPY . /app

# ������������� �����������
RUN pip install --no-cache-dir -r requirements.txt

# ������ ����������� ����� � ���������� � ����������� �������
RUN mkdir -p /app/files && \
    touch /app/database.db /app/users.db /app/bot.log && \
    chmod 666 /app/database.db /app/users.db /app/bot.log && \
    chown -R appuser:appgroup /app

# ������������� �� ������������ appuser
USER appuser

# ��������� ���������� ���������
ENV PYTHONUNBUFFERED=1

# ������� ��� ������� ����������
CMD ["python", "bot.py"]
