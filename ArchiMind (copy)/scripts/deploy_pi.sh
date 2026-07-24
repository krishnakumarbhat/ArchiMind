#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[deploy_pi] .env not found at $ENV_FILE."
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

PI_USER="${PI_USER:-pi}"
PI_HOST="${PI_HOST:-192.168.0.65}"
PI_DIR="${PI_DIR:-/home/pi/archimind}"
ARCHIMIND_IMAGE="${ARCHIMIND_IMAGE:-${DOCKER_IMAGE:-${DOCKERHUB_REPO:-krishnah27/archimind}:${DOCKER_IMAGE_TAG:-latest}}}"

echo "[deploy_pi] Deploying to ${PI_USER}@${PI_HOST}:${PI_DIR}"

echo "[deploy_pi] Preparing remote directory and copying files..."
ssh "${PI_USER}@${PI_HOST}" "mkdir -p ${PI_DIR}"
scp "$ROOT_DIR/docker-compose.pi.yml" "${PI_USER}@${PI_HOST}:${PI_DIR}/docker-compose.yml"
scp "$ENV_FILE" "${PI_USER}@${PI_HOST}:${PI_DIR}/.env"

echo "[deploy_pi] Installing Docker if missing..."
ssh "${PI_USER}@${PI_HOST}" '
set -e
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sudo sh /tmp/get-docker.sh
  sudo usermod -aG docker "$USER"
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "[deploy_pi] ERROR: docker compose plugin missing after install." >&2
  exit 1
fi
'

echo "[deploy_pi] Pulling image and starting service..."
ssh "${PI_USER}@${PI_HOST}" "cd ${PI_DIR} && ARCHIMIND_IMAGE='${ARCHIMIND_IMAGE}' docker compose pull && ARCHIMIND_IMAGE='${ARCHIMIND_IMAGE}' docker compose up -d"

echo "[deploy_pi] Checking service status..."
ssh "${PI_USER}@${PI_HOST}" "cd ${PI_DIR} && docker compose ps && docker compose logs --tail=50 web"

echo "[deploy_pi] Health check from Pi:"
ssh "${PI_USER}@${PI_HOST}" "curl -fsS http://127.0.0.1/api/status || true"

echo "[deploy_pi] Done. If your Pi LAN IP is ${PI_HOST}, open: http://${PI_HOST}"
echo "[deploy_pi] Active image: ${ARCHIMIND_IMAGE}"
