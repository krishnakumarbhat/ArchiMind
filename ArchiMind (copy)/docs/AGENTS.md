---
name: ArchiMind AGENTS
description: >
  Use when: how to run ArchiMind locally; setup dev; run worker; run tests; deploy to Raspberry Pi.
applyTo:
  - "ArchiMind/**"
exclude:
  - "ArchiMind/data/**"
  - "ArchiMind/data/vector_store/**"
  - "ArchiMind/data/chroma_db/**"
---

Purpose
- Project-scoped instructions and quickstart for ArchiMind developers and AI agents.

Primary docs
- ArchiMind/README.md
- ArchiMind/docs/RASPBERRY_PI_DEPLOYMENT.md and ArchiMind/docs/

Common tasks
- Setup environment
  - `pip install -r requirements.txt`
  - `bash scripts/setup_local.sh`
- Run application
  - `bash scripts/run_local.sh`
- Run worker
  - `bash scripts/run_worker.sh <github_repo_url>`
- Tests
  - `bash scripts/test_local.sh` or `pytest -q`

Packaging & Docker
- See `docker-compose.yml` and `Dockerfile` in the project root. Use the numbered scripts in `ArchiMind/scripts/` for build and smoke tests.

Data & exclusions
- Do not load files under `ArchiMind/data/vector_store` or `ArchiMind/data/chroma_db` into agent context; they are large binary/JSON dumps.

Notes
- Keep entries short and link to the authoritative README or docs for detailed steps.
