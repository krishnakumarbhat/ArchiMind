#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

source "$ROOT_DIR/scripts/docker_preflight.sh"

IMAGE_TAG="${IMAGE_TAG:-archimind:smoke}"
HOST_PORT="${HOST_PORT:-5050}"
CONTAINER_NAME="${CONTAINER_NAME:-archimind_smoke}"
SMOKE_DATABASE_URL="${SMOKE_DATABASE_URL:-sqlite:////app/data/archimind_smoke.db}"
SMOKE_VECTOR_BACKEND="${SMOKE_VECTOR_BACKEND:-local}"
SMOKE_GEMINI_API_KEY="${SMOKE_GEMINI_API_KEY:-}"
SMOKE_PINECONE_API_KEY="${SMOKE_PINECONE_API_KEY:-}"

if [[ ! -f .env ]]; then
  echo "[ArchiMind] ERROR: .env not found. Create it from .env.example first." >&2
  exit 1
fi

require_docker_daemon

cleanup() {
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
}

trap cleanup EXIT

docker build --pull -t "$IMAGE_TAG" .
docker run -d \
  --name "$CONTAINER_NAME" \
  --env-file .env \
  -e DATABASE_URL="$SMOKE_DATABASE_URL" \
  -e VECTOR_BACKEND="$SMOKE_VECTOR_BACKEND" \
  -e GEMINI_API_KEY="$SMOKE_GEMINI_API_KEY" \
  -e PINECONE_API_KEY="$SMOKE_PINECONE_API_KEY" \
  -e FLASK_HOST=0.0.0.0 \
  -e FLASK_PORT=5000 \
  -p "$HOST_PORT:5000" \
  "$IMAGE_TAG" >/dev/null

for attempt in $(seq 1 20); do
  if curl -fsS "http://127.0.0.1:${HOST_PORT}/api/status" >/dev/null; then
    echo "[ArchiMind] Container health check succeeded on attempt ${attempt}."
    curl -fsS "http://127.0.0.1:${HOST_PORT}/api/status"
    exit 0
  fi
  sleep 3
done

echo "[ArchiMind] ERROR: container did not become healthy in time." >&2
docker logs "$CONTAINER_NAME" >&2
exit 1