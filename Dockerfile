FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN python -m venv /opt/venv

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && pip install -r requirements.txt

FROM python:3.12-slim

LABEL org.opencontainers.image.title="ArchiMind"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/opt/venv/bin:$PATH \
    HOME=/home/archimind \
    GUNICORN_WORKERS=1 \
    GUNICORN_THREADS=4 \
    GUNICORN_TIMEOUT=240

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Remove pip and wheel from the runtime image to eliminate their CVEs.
# All packages are already installed; pip is not needed at runtime.
RUN groupadd -r archimind && useradd -r -g archimind -d /home/archimind archimind

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY . .
RUN pip install --upgrade pip setuptools wheel \
    && rm -rf /opt/venv/lib/python*/site-packages/pip /opt/venv/lib/python*/site-packages/setuptools \
    && rm -f /opt/venv/bin/pip /opt/venv/bin/pip3 /opt/venv/bin/pip3.* \
    && mkdir -p /app/data && chown -R archimind:archimind /app /opt/venv

USER archimind

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=5 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:5000/api/status', timeout=5).read()"

CMD ["/bin/sh", "-c", "exec gunicorn 'app:create_app()' --bind 0.0.0.0:${PORT:-5000} --workers ${GUNICORN_WORKERS:-1} --threads ${GUNICORN_THREADS:-4} --timeout ${GUNICORN_TIMEOUT:-240} --graceful-timeout 30 --access-logfile - --error-logfile -"]
