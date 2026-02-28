FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/archimind

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r archimind && useradd -r -g archimind -d /home/archimind archimind

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
RUN mkdir -p /app/data && chown -R archimind:archimind /app

USER archimind

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=5 \
    CMD curl -fsS http://127.0.0.1:5000/api/status || exit 1

CMD ["gunicorn", "app:create_app()", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "2", "--timeout", "180", "--access-logfile", "-", "--error-logfile", "-"]
