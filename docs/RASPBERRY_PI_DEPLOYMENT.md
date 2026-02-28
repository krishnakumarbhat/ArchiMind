# ArchiMind Raspberry Pi (ARM64) Production Deployment Guide

This guide deploys ArchiMind on Raspberry Pi at `pi@192.168.0.65` using Docker + Docker Compose.

## 1) Prerequisites

- Raspberry Pi OS 64-bit (ARM64)
- Docker Hub repository, e.g. `yourdockerhub/archimind`
- Gemini API key
- SSH access: `pi@192.168.0.65`

---

## 2) Docker Buildx (on your PC)

From project root:

```bash
docker login

docker buildx create --name archimind-builder --use --bootstrap || docker buildx use archimind-builder

# Build ARM64 image and push to Docker Hub
docker buildx build \
  --platform linux/arm64 \
  -t yourdockerhub/archimind:latest \
  -t yourdockerhub/archimind:$(date +%Y%m%d-%H%M%S) \
  --push .
```

Optional verification:

```bash
docker buildx imagetools inspect yourdockerhub/archimind:latest
```

---

## 3) Raspberry Pi setup over SSH

### 3.1 Connect

```bash
ssh pi@192.168.0.65
```

### 3.2 Install Docker + Compose plugin

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg lsb-release

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker $USER
newgrp docker

docker version
docker compose version
```

---

## 4) Deploy ArchiMind on Pi

### 4.1 Create deployment folder

```bash
mkdir -p ~/archimind && cd ~/archimind
```

### 4.2 Create `docker-compose.yml`

Use the project’s `docker-compose.yml` (copy from repo) or create this minimal production compose:

```yaml
version: "3.9"

services:
  web:
    image: yourdockerhub/archimind:latest
    container_name: archimind_web
    env_file: .env
    restart: always
    ports:
      - "80:5000"
    volumes:
      - archimind_data:/app/data
    environment:
      - DATABASE_URL=sqlite:///data/archimind_dev.db
    command: ["gunicorn", "app:create_app()", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "--graceful-timeout", "30", "--access-logfile", "-", "--error-logfile", "-"]
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:5000/api/status"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 20s

volumes:
  archimind_data:
```

### 4.3 Create `.env`

```bash
cat > .env << 'EOF'
SECRET_KEY=replace_with_long_random_secret
DATABASE_URL=sqlite:///data/archimind_dev.db
FLASK_DEBUG=False
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
ANONYMOUS_GENERATION_LIMIT=5
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
OAUTHLIB_INSECURE_TRANSPORT=0
EOF
```

### 4.4 Pull and start

```bash
docker pull yourdockerhub/archimind:latest
docker compose up -d
```

### 4.5 Verify

```bash
docker compose ps
curl -sS http://127.0.0.1/api/status
```

From another machine on LAN:

```bash
curl -sS http://192.168.0.65/api/status
```

Open browser: `http://192.168.0.65`

---

## 5) Update to latest release

On Pi:

```bash
cd ~/archimind
docker pull yourdockerhub/archimind:latest
docker compose up -d
```

---

## 6) Production debugging techniques

## A) Debugging on your PC before push

```bash
# Build amd64 for local quick test
docker build -t archimind:local .

docker run --rm -p 5000:5000 --env-file .env archimind:local

curl -sS http://127.0.0.1:5000/api/status
```

Useful checks:

```bash
docker logs -f <container_id>
docker exec -it <container_id> sh
python3 -c "import chromadb, sqlite3; print('deps ok')"
```

## B) Debugging on Raspberry Pi

```bash
cd ~/archimind
docker compose logs -f web
```

Check health/state:

```bash
docker inspect --format='{{json .State.Health}}' archimind_web | jq
```

Verify env + volume + DB file:

```bash
docker exec -it archimind_web sh
printenv | grep -E 'GEMINI_API_KEY|DATABASE_URL|FLASK_'
printenv | grep -E 'DATABASE_URL|FLASK_'
ls -lah /app/data
```

Test worker path inside container (important because app spawns `worker.py`):

```bash
docker exec -it archimind_web python3 worker.py https://github.com/LearningCircuit/local-deep-research
```

If worker fails:

- check outbound network from Pi (`curl https://api.github.com`)
- check `/app/data/status.json` updates and write permissions
- check `/app/data/chroma_db` exists and is writable

---

## 7) Reliability hardening (recommended)

- Keep `restart: always` (already set).
- Use long random `SECRET_KEY`.
- Do not commit `.env`.
- Rotate exposed API keys immediately.
- Consider Nginx/Caddy reverse proxy with TLS if exposed beyond LAN.
- Back up Docker volume:

```bash
docker run --rm -v archimind_data:/data -v $PWD:/backup busybox tar czf /backup/archimind_data_backup.tgz /data
```

---

## 8) One-command remote rollout pattern (optional)

From your PC (if compose + env already present on Pi):

```bash
ssh pi@192.168.0.65 'cd ~/archimind && docker pull yourdockerhub/archimind:latest && docker compose up -d && docker compose ps'
```
