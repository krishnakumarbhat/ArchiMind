#!/usr/bin/env bash

require_docker_cli() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "[ArchiMind] ERROR: docker is not installed or not on PATH." >&2
    return 1
  fi
}

require_docker_daemon() {
  require_docker_cli || return 1

  if docker info >/dev/null 2>&1; then
    return 0
  fi

  local docker_service_state="unknown"
  if command -v systemctl >/dev/null 2>&1; then
    docker_service_state="$(systemctl is-active docker 2>/dev/null || true)"
  fi

  echo "[ArchiMind] ERROR: the Docker CLI is installed, but the Docker daemon is not reachable." >&2

  if [[ ! -S /var/run/docker.sock ]]; then
    echo "[ArchiMind] DETAIL: /var/run/docker.sock does not exist on this host." >&2
  else
    echo "[ArchiMind] DETAIL: /var/run/docker.sock exists but docker info still failed." >&2
  fi

  case "$docker_service_state" in
    active)
      echo "[ArchiMind] DETAIL: systemd reports docker.service is active. Check docker socket permissions for the current user." >&2
      ;;
    inactive|failed|activating|deactivating)
      echo "[ArchiMind] DETAIL: systemd reports docker.service is '$docker_service_state'. Start it before retrying." >&2
      echo "[ArchiMind] FIX: sudo systemctl start docker" >&2
      ;;
    *)
      if command -v dockerd-rootless-setuptool.sh >/dev/null 2>&1; then
        echo "[ArchiMind] DETAIL: systemd did not report an active docker.service. Rootless Docker may be possible if its prerequisites are installed." >&2
        echo "[ArchiMind] FIX: dockerd-rootless-setuptool.sh check" >&2
      fi
      ;;
  esac

  return 1
}

require_docker_buildx() {
  require_docker_cli || return 1

  if ! docker buildx version >/dev/null 2>&1; then
    echo "[ArchiMind] ERROR: docker buildx is required for multi-arch builds." >&2
    return 1
  fi
}