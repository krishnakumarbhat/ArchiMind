#!/usr/bin/env bash
set -euo pipefail

PI_USER="${PI_USER:-pi}"
PI_HOST="${PI_HOST:-192.168.1.65}"
PI_DIR="${PI_DIR:-/home/pi/archimind}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCHIVE="/tmp/archimind_deploy_$(date +%s).tar.gz"

cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "[deploy_pi_build] ERROR: .env not found in project root."
  exit 1
fi

echo "[deploy_pi_build] Packaging project..."
tar \
  --exclude='.git' \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='data/chroma_db' \
  --exclude='data/temp_repo' \
  --exclude='*.pyc' \
  -czf "$ARCHIVE" .

echo "[deploy_pi_build] Uploading package to ${PI_USER}@${PI_HOST}..."
ssh "${PI_USER}@${PI_HOST}" "mkdir -p ${PI_DIR}"
scp "$ARCHIVE" "${PI_USER}@${PI_HOST}:${PI_DIR}/archimind.tar.gz"

rm -f "$ARCHIVE"

echo "[deploy_pi_build] Installing Docker on Pi if missing..."
ssh -tt "${PI_USER}@${PI_HOST}" '
set -e
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sudo sh /tmp/get-docker.sh
  sudo usermod -aG docker "$USER"
fi

if ! command -v gcc >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y build-essential python3-dev
fi

echo "[deploy_pi_build] Remote architecture info:"
uname -m || true
dpkg --print-architecture || true
'

echo "[deploy_pi_build] Extracting and launching service..."
ssh "${PI_USER}@${PI_HOST}" "cd ${PI_DIR} && tar xzf archimind.tar.gz && docker compose down || true && docker compose build --no-cache --progress=plain && docker compose up -d"

echo "[deploy_pi_build] Deployment complete. Checking health..."
ssh "${PI_USER}@${PI_HOST}" "docker compose -f ${PI_DIR}/docker-compose.yml ps && curl -fsS http://127.0.0.1/api/status || true"

echo "[deploy_pi_build] Open: http://${PI_HOST}"
