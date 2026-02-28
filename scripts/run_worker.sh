#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ $# -lt 1 ]]; then
  echo "Usage: bash scripts/run_worker.sh <github_repo_url> [analysis_log_id]"
  exit 1
fi

REPO_URL="$1"
ANALYSIS_LOG_ID="${2:-}"

mkdir -p data data/chroma_db data/temp_repo

if [[ -n "$ANALYSIS_LOG_ID" ]]; then
  python3 worker.py "$REPO_URL" "$ANALYSIS_LOG_ID"
else
  python3 worker.py "$REPO_URL"
fi
