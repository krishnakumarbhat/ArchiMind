#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "[ArchiMind] Running setup (no venv mode)..."
bash scripts/setup_local.sh

echo "[ArchiMind] Done."
echo "[ArchiMind] Start app with: bash scripts/run_local.sh"
