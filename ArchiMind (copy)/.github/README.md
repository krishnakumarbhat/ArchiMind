# GitHub Project Automation

This folder contains repository governance and CI automation.

## Contents

- `workflows/test.yml`  
  Python CI pipeline that runs on push/pull request.

- `FUNDING.yml`  
  Optional GitHub funding links.

## CI Pipeline (`workflows/test.yml`)

The workflow runs:

1. Python setup (3.11)
2. Dependency install from `requirements.txt`
3. Lint checks:
   - `black --check`
   - `isort --check-only`
   - `flake8` (critical syntax/name errors)
4. Test execution:
   - `pytest tests/ -v --maxfail=1`

## Why this setup

- Uses SQLite for CI test runs (no external database service required).
- Keeps checks fast and deterministic.
- Matches the current runtime architecture (`app.py`, `worker.py`, `services.py`).

## How to run the same checks locally

```bash
pip install -r requirements.txt
black --check .
isort --check-only .
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
pytest tests/ -v --maxfail=1
```
