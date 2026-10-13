# ArchiMind 🏗️🧠 — Autonomous Architecture Governance & Living Code Property Graph Harness

[![CI](https://github.com/krishnakumarbhat/ArchiMind/actions/workflows/test.yml/badge.svg)](https://github.com/krishnakumarbhat/ArchiMind/actions/workflows/test.yml)

ArchiMind analyzes a GitHub repository and produces:

- a deterministic **Code Property Graph** (Tree-sitter AST, NetworkX) with **100% call-edge precision** (vs 21.4% naive RAG),
- chapter-wise architecture documentation,
- high-level and low-level Mermaid diagrams via a **LangGraph evaluator-optimizer loop** with automatic fallback to deterministic diagrams,
- **sub-millisecond reverse blast-radius** impact analysis + Clean Architecture invariant checks,
- conversational project summary with a repository-scoped assistant guardrail,
- bundled **zero-compute instant showcases** (PyTorch Core, OpenClaw, Requests),
- persistent history for authenticated users —
- all in a **<24MB peak-RAM** footprint that runs on Render's 512MB tier.

Operational documentation now lives under `docs/`:

- `docs/README.md`: architecture, runtime, Docker workflow, and validation guide
- `docs/RASPBERRY_PI_DEPLOYMENT.md`: Raspberry Pi pull/run procedure using Docker Hub

## Table of Contents

1. [What You Can Do](#what-you-can-do)
2. [Architecture at a Glance](#architecture-at-a-glance)
3. [Block Diagram](#block-diagram)
4. [How It Works](#how-it-works)
5. [Quick Start (No venv)](#quick-start-no-venv)
6. [Configuration](#configuration)
7. [Run Modes](#run-modes)
8. [API Reference](#api-reference)
9. [Use Cases & Capabilities](#use-cases--capabilities)
10. [Project Structure](#project-structure)
11. [Quality, Testing & Security](#quality-testing--security)
12. [Troubleshooting](#troubleshooting)
13. [Diagrams (DOT files)](#diagrams-dot-files)
14. [Raspberry Pi Deployment](#raspberry-pi-deployment)

## What You Can Do

### Core Capabilities

- Analyze a public GitHub repository from URL (zero-clone tarball streaming).
- Build a deterministic Code Property Graph (files/classes/functions, CALLS/IMPORTS/INHERITS).
- Generate a multi-chapter architecture handbook.
- Generate HLD, LLD, and flow Mermaid payloads (self-healing reflection loop + guaranteed fallback).
- Trace downstream blast radius for any symbol in milliseconds.
- Verify presentation-isolation, acyclicity, and domain-purity invariants.
- "Challenge Me" onboarding tasks mined from untested code seams.
- View output in a 5-tab studio (canvas, handbook, impact, assistant, research).

### User Experience Features

- Anonymous mode with per-session limit (default 5 analyses).
- Authenticated mode with unlimited usage and saved history.
- OAuth (Google) optional; classic email/password supported.
- Repository history API stored in the configured relational database.

## Architecture at a Glance

### Main Runtime Components

- `app.py`: Flask web app, routes, auth, SQLAlchemy models, analysis dispatch, guarded assistant.
- `worker.py`: Background execution pipeline (tarball ingest → Chroma index → CPG → generate → repair).
- `src/`: modular engine — `config/`, `ingestion/` (tarball + subtree streaming), `cpg/` (Tree-sitter + NetworkX + closure gate), `orchestration/` (LangGraph evaluator-optimizer, deterministic diagrams), `governance/` (blast radius, invariants), `agentic/` (CPG tools, Challenge-Me harness), `security/` (prompt guardrail, model scrubber), `storage/` (SQLite cache + bundled golden fixtures).
- `services.py`:
  - `RepositoryService` (preview + clone + file extraction)
  - `VectorStoreService` (LlamaIndex AST chunking + ChromaDB/Pinecone/local indexing)
  - `DocumentationService` (context-driven docs/HLD/LLD/summary/chat)
- `oauth_utils.py`: OAuth + lightweight in-process cache helpers.

### End-to-End Flow

1. User submits repository URL (`POST /api/analyze`) or opens a golden demo (`/workspace/golden:<id>`).
2. App validates request, rate limits, and enforces single-job concurrency (`429` when busy).
3. App records `AnalysisLog` entry and spawns `worker.py` subprocess.
4. Worker streams a shallow tarball (no clone), builds the ChromaDB index and the deterministic CPG.
5. LangGraph retrieves relevant files first, then precise code chunks; CPG context grounds generation.
6. Each diagram passes a grammar validator; failures reflect with the exact error (≤3 attempts), else a deterministic code-graph diagram is substituted — the canvas never shows a syntax error.
7. Worker writes status/result to `data/status_<id>.json` and updates DB log.

## Block Diagram

```mermaid
flowchart TD
        U[User / API Client] --> A[Flask API]
        A --> W[Worker Process]

        W --> R{Repository Ingestion Strategy}
        R -->|Fast path| G[GitHub API + Raw Content Scraping]
        R -->|Fallback| C[Selective Local Clone]

        G --> I[Index Builder]
        C --> I

        I --> S[Tier 1: File Summaries in Vector Store]
        I --> K[Tier 2: AST Code Chunks in Vector Store]

        Q[LangGraph Query Orchestrator] --> S
        Q --> K
        S --> Q
        K --> Q

        Q --> D[Documentation + HLD + LLD Generation]
        D --> J[(Relational DB + status.json)]
        D --> U
```

## How It Works

### 1) Ingestion strategy (speed first)

- For GitHub URLs, the worker first uses GitHub API + raw file endpoints to **scrape important repository files**.
- It prioritizes files such as `README*`, `docs/*`, architecture/design files, and core source entry points (`app`, `api`, `service`, `worker`, etc.).
- For very large repositories, it fetches a scored subset instead of cloning everything.
- Tarball streaming is the primary path; selective remote fetch and local clone remain as fallbacks.

### 2) Hierarchical index

- **Tier 1 (File summaries):** each file gets a compact summary for coarse retrieval.
- **Tier 2 (Code chunks):** source is chunked by AST blocks (functions/classes/methods) where possible using LlamaIndex `CodeSplitter`.
- Every chunk stores metadata: `file_path`, `language`, `function_name`, `github_url`, line range.
- Production deployments can persist vectors in Pinecone and relational data in PostgreSQL.

### 3) Query pipeline

- LangGraph runs a 2-step retrieval graph:
  1. query summary collection to find relevant files,
  2. query chunk collection scoped to those files.
- Returned context is assembled with metadata-rich headers so downstream HLD/LLD generation stays grounded.

## Quick Start (No venv)

### Prerequisites

- Python 3.10+ (3.11 recommended)
- Git
- Gemini API key for production-quality documentation generation

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

For local development, tests, and linting, use `bash scripts/setup_local.sh`, which installs the additional packages from `requirements-dev.txt`.

### 2) Create environment file

```bash
cp .env.example .env
```

Set at least:

- `SECRET_KEY=...`
- `GEMINI_API_KEY=...`
- `DATABASE_URL=postgresql+psycopg://user:password@host:5432/postgres`

### 3) One-command setup + run

```bash
bash scripts/setup_local.sh
bash scripts/run_local.sh
```

Open `http://127.0.0.1:5000`.

### 4) Run a sample analysis

Use this sample repository URL in the UI:

`https://github.com/LearningCircuit/local-deep-research`

Or via API:

```bash
curl -X POST http://127.0.0.1:5000/api/analyze \
    -H "Content-Type: application/json" \
    -d '{"repo_url":"https://github.com/LearningCircuit/local-deep-research"}'

curl http://127.0.0.1:5000/api/status
```

### 5) Instant demos (zero compute)

Three pre-computed showcases ship with the repo — open one, no analysis run needed:

| Demo | Scope | Open |
|---|---|---|
| PyTorch Core | `torch/nn/modules` + `torch/optim` | `/workspace/golden:pytorch` |
| OpenClaw | `src/agents` runtime subsystem | `/workspace/golden:openclaw` |
| Requests HTTP | `src/requests` client | `/workspace/golden:requests` |

## Configuration

Primary configuration lives in `.env` and `src/config/` (`_00_settings.py`, `_01_constants.py`, `_02_app_config.py`).

### Required Environment Variables

| Variable       | Required | Description                              |
| -------------- | -------- | ---------------------------------------- |
| `SECRET_KEY`   | Yes      | Flask session/signing key                |
| `GEMINI_API_KEY` | Yes for neural mode | API key for hosted documentation generation |
| `DATABASE_URL` | No       | Supports PostgreSQL/Supabase in production and SQLite locally |
| `PINECONE_API_KEY` / `PINECONE_INDEX_NAME` | No | Enables Pinecone-backed vector persistence |

### Optional Environment Variables

| Variable                                    | Description                         |
| ------------------------------------------- | ----------------------------------- |
| `FLASK_DEBUG`                               | `True/False` for local debugging    |
| `FLASK_HOST`                                | Bind host (default `127.0.0.1`)     |
| `FLASK_PORT`                                | Bind port (default `5000`)          |
| `DOCUMENTATION_MODEL` / `CHAT_MODEL`        | Generation model selection          |
| `GEMINI_THINKING_LEVEL`                     | Thinking level for generation       |
| `GEMINI_API_VERSION`                        | Generation HTTP API version         |
| `MAX_CONCURRENT_JOBS`                       | Concurrent analyses (keep 1 on 512MB tier) |
| `TARBALL_MAX_MB` / `TARBALL_MAX_FILES`      | Zero-clone ingestion bounds         |
| `MERMAID_MAX_RETRIES`                       | Diagram self-healing reflection cap |
| `ANONYMOUS_GENERATION_LIMIT`                | Free analyses per anonymous session |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Optional Google OAuth login         |
| `OAUTHLIB_INSECURE_TRANSPORT`               | Local HTTP OAuth testing toggle     |

### Retrieval Configuration (`src/config/`)

- Tier 1: file-level summaries stored in the configured vector backend
- Tier 2: AST-based code chunks stored in the configured vector backend
- Query orchestration: LangGraph summary-first retrieval pipeline

## Run Modes

### Web App

```bash
bash scripts/run_local.sh
```

### Worker only (manual)

```bash
bash scripts/run_worker.sh https://github.com/owner/repo
```

### Tests

```bash
bash scripts/test_all.sh
```

### Docker

```bash
bash scripts/docker_build.sh ${DOCKER_USERNAME:-krishnah27}/archimind latest
```

Or run the published image directly:

```bash
docker run -p 5000:5000 -v archimind_data:/app/data --env-file .env \
  ${DOCKER_USERNAME:-krishnah27}/archimind:latest
```

The production image now installs runtime-only dependencies and uses a multi-stage build so test and lint tooling is not shipped in the container.

### Render deployment (512MB tier)

1. Push this branch and create a Render Web Service from the repo (Docker runtime).
2. Set env vars: `SECRET_KEY`, `DATABASE_URL` (or bundled SQLite via the `archimind_data` volume),
   `GEMINI_API_KEY`, `VECTOR_BACKEND=chroma`. No `PINECONE_*` needed.
3. Keep 1 worker / 4 threads (Dockerfile defaults); the app 429s concurrent analyses itself.
4. Health check: `GET /api/status` (already wired in `Dockerfile` and compose files).

For Raspberry Pi deployment instructions, see `docs/RASPBERRY_PI_DEPLOYMENT.md`.

## API Reference

### `POST /api/analyze`

Starts asynchronous analysis.

Request:

```json
{
  "repo_url": "https://github.com/owner/repo"
}
```

Responses:

- `202`: started (poll `status_url`, then open `doc_url` or `/workspace/<analysis_id>`)
- `400`: missing/invalid input
- `403`: anonymous limit reached
- `429`: another analysis is running (single-job guard; retry shortly)

### `GET /api/status`

Returns analysis status and result payload.

Common statuses:

- `idle`
- `processing`
- `completed`
- `error`

### `GET /api/check-limit`

Returns whether current actor can submit analysis.

### `GET /api/preview`

Returns a lightweight GitHub repository preview before running a full analysis.

### `POST /api/chat`

Answers a repository-specific question using the stored index plus deterministic CPG tools
(`trace_symbol_impact`, `verify_architecture_rules`, `get_symbol_ast`). Questions are capped
at 250 characters, scoped to repository reasoning by a guardrail (out-of-scope prompts are
rejected with an explicit message), and anonymous sessions get 5 questions. Model/provider
names are scrubbed from all responses (`Engine: ArchiMind Neural Graph Core`).

### `GET /api/golden` and `GET /api/golden/<id>`

Light list and full workspace payload for the bundled instant demos (no analysis run needed).

### `GET /api/blast-radius?symbol=<name>&golden=<id>&analysis_id=<id>`

Transitive downstream impact (callers, instantiators, subclasses) with edge count and latency.

### `GET /api/challenge?golden=<id>&analysis_id=<id>`

One onboarding coding challenge mined from an untested code seam (description, target file,
starter code, failing test).

### `GET /api/history` (authenticated)

Returns cached/history list for logged-in user.

### `GET /api/history/<repo_id>` (authenticated)

Returns full stored artifacts (docs/HLD/LLD) for one repository.

## Use Cases & Capabilities

### 1) Architecture Discovery

- Input: unfamiliar repository URL
- Output: chapter-wise architecture handbook
- Benefit: fast onboarding for new developers

### 2) Design Review Preparation

- Input: actively developed service repo
- Output: HLD + LLD diagrams and narrative summary
- Benefit: reusable artifact for review/ADR conversations

### 3) Team Knowledge Retention

- Input: recurring analyses for authenticated users
- Output: repository history with latest generated artifacts
- Benefit: centralized memory of architecture snapshots

### 4) Portfolio / Due Diligence Analysis

- Input: external OSS repos
- Output: standardized architecture summaries across projects
- Benefit: compare technical shape quickly

## Project Structure

```text
ArchiMind/
├── main.py                 # production entrypoint (WSGI: main:app)
├── Dockerfile / docker-compose.yml / docker-compose.pi.yml
├── .env.example / .gitignore / pyproject.toml / requirements.txt / LICENSE
├── src/                    # all application code (absolute src.* imports)
│   ├── config/             # Pydantic settings, constants, app config bridge
│   ├── ingestion/          # tarball + subtree streaming, file filter
│   ├── cpg/                # ASTExtractor, CodePropertyGraphBuilder, InheritanceClosureGate
│   ├── orchestration/      # LangGraph state, MermaidEvaluatorOptimizer, CPGDiagramCompiler, worker
│   ├── governance/         # ReverseBlastRadiusEngine, ArchitectureInvariantChecker
│   ├── agentic/            # CPGInspectionToolSuite, SWEChallengeHarness
│   ├── security/           # prompt guardrail, model scrubber
│   ├── storage/            # models, SQLite cache, bundled golden_fixtures/
│   ├── services/           # repository/vector/documentation services, OAuth
│   └── web/                # Flask application factory + routes
├── templates/              # 00_base, 01_landing, 02_studio, doc, auth pages
├── static/css|js/          # tokens, landing, studio, canvas, pan/zoom, tabs, challenge
├── tests/unit|integration|e2e/
├── scripts/                # run_local, test_all, docker_build, deploy_pi, maintenance/
└── docs/                   # architecture, profiling, leaderboard, diagrams
```

## Quality, Testing & Security

### Testing

```bash
bash scripts/test_all.sh   # unit + integration + legacy + Playwright e2e + ruff
```

### Linting / Formatting / Types

```bash
python3 -m ruff check src/ scripts/ 00_main.py app.py worker.py
python3 -m black src/ scripts/build_golden_cache.py 00_main.py
python3 -m mypy src/   # strict
```

### Security Notes

- Passwords use `pbkdf2:sha256` hashing.
- Avoid committing `.env` and generated data.
- Rotate exposed API keys immediately.

## Troubleshooting

### SQLite `unable to open database file`

- Ensure `data/` exists and is writable.
- Use absolute or normalized SQLite path in `DATABASE_URL`.
- Run `bash scripts/setup_local.sh` to bootstrap required folders.

### `403` limit reached

- Anonymous session hit configured cap.
- Sign in or clear browser session data.

### Empty or weak retrieval context

- Re-run analysis to rebuild summary + chunk collections.
- Verify target repository has supported text/code files.

### OAuth issues in local dev

- Set callback URLs correctly in Google Console.
- Keep `OAUTHLIB_INSECURE_TRANSPORT=1` only for local HTTP.

## Diagrams (DOT files)

Generated architecture/use-case Graphviz files are included:

- `docs/diagrams/hld.dot`
- `docs/diagrams/hld.drawio`
- `docs/diagrams/lld.dot`
- `docs/diagrams/lld.drawio`
- `docs/diagrams/flow.dot`
- `docs/diagrams/flow.drawio`
- `docs/diagrams/uml.dot`
- `docs/diagrams/uml.drawio`
- `docs/diagrams/use_cases.dot`
- `docs/diagrams/use_cases.drawio`

Render any DOT file:

```bash
dot -Tpng docs/diagrams/hld.dot -o hld.png
```

Regenerate all draw.io files from the DOT sources:

```bash
/usr/bin/python3 scripts/02_convert_dot_to_drawio.py
```

## Raspberry Pi Deployment

For ARM64 production deployment with Docker Buildx + Docker Compose, see:

- `docs/RASPBERRY_PI_DEPLOYMENT.md`

## License

MIT (see `LICENSE` if present in your distribution).
