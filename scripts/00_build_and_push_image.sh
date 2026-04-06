#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

source "$ROOT_DIR/scripts/docker_preflight.sh"

DOCKERHUB_REPO="${1:-${DOCKERHUB_REPO:-krishnah27/archimind}}"
DOCKER_IMAGE_TAG="${2:-${DOCKER_IMAGE_TAG:-latest}}"
TIMESTAMP_TAG="${TIMESTAMP_TAG:-$(date +%Y%m%d-%H%M%S)}"
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"
PUSH_IMAGE="${PUSH_IMAGE:-1}"
BUILDER_NAME="${BUILDER_NAME:-archimind-builder}"
CLEAN_OLD_LOCAL_IMAGES="${CLEAN_OLD_LOCAL_IMAGES:-1}"

require_docker_daemon
require_docker_buildx

cleanup_old_repo_images() {
  if [[ "$CLEAN_OLD_LOCAL_IMAGES" != "1" ]]; then
    return
  fi

  mapfile -t image_ids < <(
    docker images --format '{{.Repository}}:{{.Tag}} {{.ID}}' |
      awk -v repo="$DOCKERHUB_REPO" '$1 ~ ("^" repo ":") { print $2 }' |
      sort -u
  )

  if (( ${#image_ids[@]} == 0 )); then
    return
  fi

  echo "[ArchiMind] Removing ${#image_ids[@]} existing local images for $DOCKERHUB_REPO"
  docker rmi -f "${image_ids[@]}" >/dev/null 2>&1 || true
}

if ! docker buildx inspect "$BUILDER_NAME" >/dev/null 2>&1; then
  docker buildx create --name "$BUILDER_NAME" --use >/dev/null
else
  docker buildx use "$BUILDER_NAME" >/dev/null
fi

docker buildx inspect --bootstrap >/dev/null
cleanup_old_repo_images

build_args=(
  build
  --pull
  --platform "$PLATFORMS"
  -t "$DOCKERHUB_REPO:$DOCKER_IMAGE_TAG"
  -t "$DOCKERHUB_REPO:$TIMESTAMP_TAG"
)

if [[ "$PUSH_IMAGE" == "1" ]]; then
  build_args+=(--push)
elif [[ "$PLATFORMS" == *","* ]]; then
  echo "[ArchiMind] ERROR: multi-platform builds require PUSH_IMAGE=1." >&2
  exit 1
else
  build_args+=(--load)
fi

build_args+=(.)

echo "[ArchiMind] Building image for $PLATFORMS"
echo "[ArchiMind] Repository: $DOCKERHUB_REPO"
echo "[ArchiMind] Tags: $DOCKER_IMAGE_TAG, $TIMESTAMP_TAG"

docker buildx "${build_args[@]}"

echo "[ArchiMind] Image build complete."
echo "[ArchiMind] Pi pull target: $DOCKERHUB_REPO:$DOCKER_IMAGE_TAG"
echo "[ArchiMind] Timestamp tag: $DOCKERHUB_REPO:$TIMESTAMP_TAG"