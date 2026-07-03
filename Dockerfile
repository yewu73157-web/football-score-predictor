FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FOOTBALL_HOST=0.0.0.0
ENV FOOTBALL_DEBUG=0

CMD gunicorn app:app --bind 0.0.0.0:${PORT:-8765} --workers 1 --threads 8 --timeout 45
