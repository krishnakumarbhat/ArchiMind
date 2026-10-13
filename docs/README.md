# ArchiMind Documentation

This document is the operational reference for the current ArchiMind runtime. The root `README.md` stays intentionally short for repository landing-page use; the detailed setup, deployment, and diagram inventory live here.

## Overview

ArchiMind analyzes a GitHub repository, retrieves the most relevant files and code chunks, and generates:

- an architecture handbook,
- high-level and low-level Mermaid diagrams,
- a short onboarding summary,
- per-user history for authenticated sessions.

The runtime is the Flask + worker architecture; documentation generation uses the
configured neural generation backend with high-reasoning settings (see `DOCUMENTATION_MODEL`
and `GEMINI_THINKING_LEVEL`).

If `GEMINI_API_KEY` is missing or generation fails at runtime, the service falls back to the local heuristic generator so the application can still operate.

## Runtime Flow

1. `app.py` accepts `POST /api/analyze`, validates the request, rate-limits, and enforces the single-job guard (`429` while busy).
2. `app.py` inserts an `AnalysisLog` row and starts `worker.py` as a subprocess with repo URL + analysis ID. `/` serves the landing page; `/workspace/<id>` serves the 5-tab studio.
3. `worker.py` streams a shallow tarball via `src/ingestion` (no clone), falling back to legacy remote/clone collection.
4. `VectorStoreService` indexes into ChromaDB (default, disk-backed), Pinecone (opt-in), or local JSON; `src/cpg` builds the deterministic Code Property Graph in parallel.
5. CPG context grounds `DocumentationService` (Gemini handbook/diagrams, local-heuristic fallback); each diagram passes the LangGraph evaluator-optimizer validator with deterministic fallback.
6. `worker.py` writes `data/status_<analysis_id>.json` (completed results are shareable cross-session), updates `AnalysisLog`, and persists history for authenticated users.

## Environment Variables

Required for production use:

- `SECRET_KEY`: Flask signing key.
- `GEMINI_API_KEY`: Gemini Developer API key.

Core optional settings:

- `DATABASE_URL`: defaults to `sqlite:///data/archimind_dev.db`.
- `DOCUMENTATION_MODEL`: defaults to the configured generation model (see `.env.example`).
- `CHAT_MODEL`: defaults to the same value as `DOCUMENTATION_MODEL`.
- `GEMINI_THINKING_LEVEL`: defaults to `high`.
- `GEMINI_API_VERSION`: defaults to `v1alpha` so preview models work.
- `DOCUMENTATION_CONTEXT_CHAR_LIMIT`: caps retrieved context before generation.

Deployment defaults:

- `ARCHIMIND_IMAGE`: Docker image reference used by the Pi compose file.
- `DOCKERHUB_REPO`: repository used by the build/push script.
- `DOCKER_IMAGE_TAG`: mutable deployment tag, usually `latest`.
- `PI_USER`, `PI_HOST`, `PI_DIR`: SSH deployment target for `scripts/deploy_pi.sh`.

## Local Development

1. Copy `.env.example` to `.env`.
2. Set `SECRET_KEY` and `GEMINI_API_KEY`.
3. Run `bash scripts/setup_local.sh`.
4. Start the app with `bash scripts/run_local.sh`.
5. Run the test suite with `bash scripts/test_all.sh`.

The status API returns the latest worker payload at `GET /api/status`. After a completed analysis, the result now includes `generation_backend`, which makes it obvious whether the run used Gemini or the local fallback.

## Docker Workflow

Use the scripts in `scripts/` instead of ad hoc Docker commands so the same flow can be repeated on another machine.

The Docker image now installs runtime-only dependencies from `requirements.txt`. Development-only tooling lives in `requirements-dev.txt` and is intentionally excluded from the production container to reduce the image attack surface and vulnerability count.

### Build and Push

The build machine must have a reachable Docker daemon before this script can create or bootstrap the Buildx builder:

```bash
docker info
sudo systemctl start docker
```

```bash
bash scripts/docker_build.sh krishnah27/archimind latest
```

Behavior:

- builds a multi-arch image for `linux/amd64,linux/arm64`,
- tags both `latest` and a timestamp tag,
- pushes directly to Docker Hub by default.

Important: pushing still requires that your local Docker daemon is running and your local Docker CLI is already authenticated to Docker Hub.

### Smoke Test the Container

```bash
# smoke test is built into scripts/docker_build.sh
```

This builds the local image, starts it on port `5050`, and curls `/api/status` until the container becomes healthy. If the Docker daemon is down, the script now exits immediately with a targeted fix instead of failing later during the build.

## Raspberry Pi Deployment

The Pi deployment path assumes the image is already present in Docker Hub and publicly pullable by the Pi.

Recommended sequence:

1. Build and push the multi-arch image with `scripts/docker_build.sh`.
2. The builder smoke-tests the image automatically.
3. Set `ARCHIMIND_IMAGE`, `PI_HOST`, and other Pi variables in `.env`.
4. Run `bash scripts/deploy_pi.sh`.

The full Pi runbook is in `docs/RASPBERRY_PI_DEPLOYMENT.md`.

## Diagram Inventory

Source diagrams remain in Graphviz DOT so they are diffable in Git. Matching draw.io files are generated for editing in diagrams.net.

- `docs/diagrams/flow.dot` and `docs/diagrams/flow.drawio`
- `docs/diagrams/hld.dot` and `docs/diagrams/hld.drawio`
- `docs/diagrams/lld.dot` and `docs/diagrams/lld.drawio`
- `docs/diagrams/use_cases.dot` and `docs/diagrams/use_cases.drawio`
- `docs/diagrams/uml.dot` and `docs/diagrams/uml.drawio`

To regenerate the draw.io XML files after editing any DOT source:

```bash
/usr/bin/python3 scripts/02_convert_dot_to_drawio.py
```

## Validation Checklist

- `bash scripts/test_all.sh`
- `bash scripts/docker_build.sh` (includes smoke test)
- verify Docker Hub tags after `scripts/docker_build.sh`
- on Pi, run `docker compose ps` and `curl -fsS http://127.0.0.1/api/status`

## Current Constraints

- The repository keeps its existing file layout. The current change set does not rename runtime modules into numbered files because that would be a large breaking refactor across imports, tests, and deployment assets.
- The retrieval/indexing path is still local-first and lightweight. Gemini is now used for documentation generation, not for every retrieval operation.
- Docker Hub push can only succeed if the local machine is already authenticated and has permission to publish to the target repository.