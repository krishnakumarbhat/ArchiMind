#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export DATABASE_URL="${DATABASE_URL:-sqlite:///:memory:}"
export SECRET_KEY="${SECRET_KEY:-test-secret-key}"

pytest tests/ -v --cov=.
