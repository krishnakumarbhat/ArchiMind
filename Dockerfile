# ArchiMind production image (ARM64-compatible)
FROM python:3.11-slim-bullseye AS builder

ARG DEBIAN_FRONTEND=noninteractive

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN set -eux; \
        ARCH="$(dpkg --print-architecture)"; \
        cp requirements.txt requirements.resolved.txt; \
        if [ "$ARCH" = "armhf" ] || [ "$ARCH" = "armel" ]; then \
            echo "[Docker build] ARM 32-bit detected ($ARCH): removing chromadb dependency"; \
            grep -v -E '^chromadb==' requirements.resolved.txt > requirements.tmp && mv requirements.tmp requirements.resolved.txt; \
        fi; \
        pip install --upgrade pip && pip install --no-cache-dir --user -r requirements.resolved.txt


FROM python:3.11-slim-bullseye

ARG DEBIAN_FRONTEND=noninteractive

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/archimind/.local/bin:$PATH \
    HOME=/home/archimind

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r archimind && useradd -r -g archimind archimind

WORKDIR /app

COPY --from=builder /root/.local /home/archimind/.local
COPY . .

RUN mkdir -p /app/data && chown -R archimind:archimind /app

USER archimind

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=5 \
    CMD curl -fsS http://127.0.0.1:5000/api/status || exit 1

CMD ["gunicorn", "app:create_app()", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "--graceful-timeout", "30", "--access-logfile", "-", "--error-logfile", "-"]
