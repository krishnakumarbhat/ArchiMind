#!/usr/bin/env bash
set -euo pipefail

PI_USER="${PI_USER:-pi}"
PI_HOST="${PI_HOST:-192.168.1.65}"
PI_DIR="${PI_DIR:-/home/pi/archimind}"

echo "[autostart] Installing reboot autostart on ${PI_USER}@${PI_HOST}"

ssh "${PI_USER}@${PI_HOST}" "bash -s" <<'REMOTE'
set -euo pipefail
PI_DIR="${PI_DIR:-/home/pi/archimind}"

# Ensure Docker daemon starts on boot
sudo systemctl enable docker
sudo systemctl start docker

mkdir -p "${PI_DIR}"

CRON_LINE="@reboot cd ${PI_DIR} && /usr/bin/docker compose up -d >> ${PI_DIR}/cron-start.log 2>&1"

# Install idempotently
( crontab -l 2>/dev/null | grep -v "docker compose up -d"; echo "$CRON_LINE" ) | crontab -

echo "[autostart] Installed crontab entry:"
crontab -l | grep "docker compose up -d" || true
REMOTE

echo "[autostart] Done. Reboot Pi to verify: sudo reboot"
