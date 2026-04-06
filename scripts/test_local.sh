#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p data

export DATABASE_URL="${DATABASE_URL:-sqlite:///$ROOT_DIR/data/test_suite.db}"
export SECRET_KEY="${SECRET_KEY:-test-secret-key}"
export VECTOR_BACKEND="${VECTOR_BACKEND:-local}"
export GEMINI_API_KEY="${GEMINI_API_KEY:-}"
export PINECONE_API_KEY="${PINECONE_API_KEY:-}"

pytest tests/ -v --cov=.
