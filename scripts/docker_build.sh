#!/usr/bin/env bash
# Multi-platform Docker builder, pusher, and smoke-tester for ArchiMind.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

source "$ROOT_DIR/scripts/docker_preflight.sh"

DOCKERHUB_REPO="${1:-${DOCKERHUB_REPO:-krishnah27/archimind}}"
DOCKER_IMAGE_TAG="${2:-${DOCKER_IMAGE_TAG:-latest}}"
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"
PUSH_IMAGE="${PUSH_IMAGE:-1}"
BUILDER_NAME="${BUILDER_NAME:-archimind-builder}"

require_docker_daemon
require_docker_buildx

echo "[docker_build] Building ${DOCKERHUB_REPO}:${DOCKER_IMAGE_TAG} for ${PLATFORMS}..."
docker buildx build --builder "$BUILDER_NAME" --platform "$PLATFORMS" \
  -t "${DOCKERHUB_REPO}:${DOCKER_IMAGE_TAG}" --push="$PUSH_IMAGE" .

if [[ "$PUSH_IMAGE" == "1" ]]; then
  echo "[docker_build] Pushed ${DOCKERHUB_REPO}:${DOCKER_IMAGE_TAG}"
fi

echo "[docker_build] Smoke test (amd64 pull + /api/status)..."
docker run -d --rm --name archimind-smoke -p 5129:5000 "${DOCKERHUB_REPO}:${DOCKER_IMAGE_TAG}" >/dev/null
trap 'docker stop archimind-smoke >/dev/null 2>&1 || true' EXIT
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:5129/api/status >/dev/null 2>&1; then
    echo "[docker_build] Smoke test passed."
    exit 0
  fi
  sleep 4
done
echo "[docker_build] ERROR: container never became healthy." >&2
exit 1
