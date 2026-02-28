#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p data data/chroma_db data/temp_repo

if [[ ! -f .env ]]; then
  echo "[ArchiMind] ERROR: .env not found. Run: bash scripts/setup_local.sh"
  exit 1
fi

python3 app.py
