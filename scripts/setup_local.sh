#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[ArchiMind] Local setup starting..."

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ArchiMind] ERROR: python3 is not installed."
  exit 1
fi

if ! command -v pip >/dev/null 2>&1; then
  echo "[ArchiMind] ERROR: pip is not installed."
  exit 1
fi

mkdir -p data data/chroma_db data/temp_repo

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "[ArchiMind] Created .env from .env.example"
else
  echo "[ArchiMind] .env already exists; keeping your values"
fi

pip install -r requirements.txt

echo "[ArchiMind] Setup complete."
echo "[ArchiMind] Next: edit .env (GEMINI_API_KEY, SECRET_KEY), then run: bash scripts/run_local.sh"
