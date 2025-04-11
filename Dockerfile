# ���������� ����������� ����� Python
FROM python:3.9-slim

RUN groupadd -g 1000 appgroup && \
    useradd -m -u 1000 -g appgroup appuser

RUN ../touch bot.log && \
    chown -R appuser:appgroup .

# ������������� ������� ����������
WORKDIR /app

# �������� ����� �������
COPY . /app

# ������������� �����������
RUN pip install --no-cache-dir -r requirements.txt

# ��������� ���������� ���������
ENV PYTHONUNBUFFERED=1


# ������� ��� ������� ����������
CMD ["python", "bot.py"]
