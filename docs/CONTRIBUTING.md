# Contributing to ArchiMind

ArchiMind accepts focused production-minded contributions. Keep changes small, testable, and consistent with the existing Flask plus worker architecture.

## Contribution Rules

- Do not commit secrets, tokens, `.env`, database dumps, or generated runtime data.
- Keep local development on `VECTOR_BACKEND=chroma` unless you are explicitly validating a Pinecone deployment path.
- Prefer root-cause fixes over UI-only or script-only workarounds.
- Preserve the existing module boundaries unless a larger refactor is agreed first.
- Update documentation when behavior, environment variables, scripts, or diagrams change.

## Local Setup

1. Copy `.env.example` to `.env` and fill in the required values.
2. Run `bash scripts/setup_local.sh`.
3. Start the app with `bash scripts/run_local.sh`.
4. Run tests with `bash scripts/test_local.sh`.

Recommended local defaults:

- `DATABASE_URL=sqlite:///data/archimind_dev.db` for isolated local work.
- `VECTOR_BACKEND=chroma` for local vector indexing.
- Set `GEMINI_API_KEY` only if you need to validate the Gemini generation path.

## Coding Expectations

- Keep Python changes PEP 8 compliant and avoid unrelated formatting churn.
- Maintain single-responsibility boundaries across `app.py`, `worker.py`, and `services.py`.
- Add or update tests for behavior changes, especially request flow, worker status handling, and persistence logic.
- Use environment variables for every secret or deployment-specific value.

## Database and Retrieval Changes

- Production deployments are expected to use Supabase PostgreSQL.
- Local testing may continue using SQLite when that is faster or more isolated.
- Pinecone support must remain optional and env-driven.
- Changes to `models.py`, `oauth_utils.py`, or `services.py` should include regression coverage for existing history and analysis flows.

## Documentation and Diagrams

- Keep detailed operational notes in `docs/README.md`.
- Maintain diagrams directly as `.drawio` files in `docs/diagrams/`.
- Do not reintroduce `.dot` sources or diagram conversion scripts.
- If you change architecture, update the HLD, LLD, UML, and use-case diagrams in the same pull request.

## Pull Request Checklist

Before opening a pull request, verify all of the following:

1. `bash scripts/test_local.sh` passes.
2. Any changed user flow was tested locally.
3. Relevant docs were updated.
4. No secret or machine-specific value appears in the diff.
5. Docker-related changes were at least smoke-tested when practical.

## Suggested PR Format

- Summary: what changed and why.
- Risk: any migration, config, or deployment impact.
- Validation: commands run and behavior verified.

This keeps reviews fast and makes release decisions easier.