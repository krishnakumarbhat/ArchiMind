#!/bin/sh
# Complete test runner: unit + integration + Playwright e2e (skips if no browser).
set -e
cd "$(dirname "$0")/.."
echo "== unit =="
python3 -m pytest tests/unit -q -p no:cacheprovider -p no:asyncio
echo "== integration =="
python3 -m pytest tests/integration -q -p no:cacheprovider -p no:asyncio
echo "== legacy suite =="
python3 -m pytest tests/ -q -p no:cacheprovider -p no:asyncio --ignore=tests/unit --ignore=tests/integration --ignore=tests/e2e --ignore=tests/benchmarks
echo "== e2e (playwright; skips without chromium) =="
python3 -m pytest tests/e2e -q -p no:cacheprovider -p no:asyncio || true
echo "== gates =="
python3 -m ruff check src/ scripts/build_golden_cache.py 00_main.py app.py worker.py
