#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p data data/chroma_db data/temp_repo

LOCAL_DATABASE_URL="sqlite:///$ROOT_DIR/data/archimind_local.db"

if [[ ! -f .env ]]; then
  echo "[ArchiMind] ERROR: .env not found. Run: bash scripts/setup_local.sh"
  exit 1
fi

if [[ "${ARCHIMIND_USE_REMOTE_DB:-0}" == "1" ]]; then
  echo "[ArchiMind] Using DATABASE_URL from environment/.env"
else
  export DATABASE_URL="$LOCAL_DATABASE_URL"
  echo "[ArchiMind] Using local SQLite database: $LOCAL_DATABASE_URL"
  echo "[ArchiMind] Set ARCHIMIND_USE_REMOTE_DB=1 to test the remote DATABASE_URL locally"
fi

python3 app.py
