# ���������� ����������� ����� Python
FROM python:3.9-slim

RUN groupadd -g 1000 appgroup && \
    useradd -m -u 1000 -g appgroup appuser

# ������������� ������� ����������
WORKDIR /app

RUN touch /app/bot.log && \
    chown -R appuser:appgroup .


# �������� ����� �������
COPY . /app

# ������������� �����������
RUN pip install --no-cache-dir -r requirements.txt

# ��������� ���������� ���������
ENV PYTHONUNBUFFERED=1


# ������� ��� ������� ����������
CMD ["python", "bot.py"]
