# The ArchiMind Story — A File-by-File Walkthrough

> Every tracked file in this repository, what it does, and how it connects to the others.
> Written by reading all 110 tracked files (~11,700 lines).
> Companion docs: `README.md` (landing page), `docs/README.md` (operations), `docs/profiling.md` (measured budgets).

---

## Table of Contents

1. [The One-Paragraph Story](#1-the-one-paragraph-story)
2. [The Shape of the System](#2-the-shape-of-the-system)
3. [The Request Lifecycle, End to End](#3-the-request-lifecycle-end-to-end)
4. [Root Files](#4-root-files)
5. [`src/` — The Engine](#5-src--the-engine)
6. [`static/` — Frontend](#6-static--frontend)
7. [`templates/` — Server-Rendered Shells](#7-templates--server-rendered-shells)
8. [`scripts/` — Operations](#8-scripts--operations)
9. [`tests/` — The Safety Net](#9-tests--the-safety-net)
10. [`docs/` and `.github/`](#10-docs-and-github)
11. [Data Flow Diagram: Who Calls Whom](#11-data-flow-diagram-who-calls-whom)
12. [Configuration Surface](#12-configuration-surface)
13. [Where the README Lies](#13-where-the-readme-lies)
14. [Untracked and Empty Things](#14-untracked-and-empty-things)

---

## 1. The One-Paragraph Story

You paste a GitHub URL. ArchiMind does **not** clone the repo. It streams a
`codeload.github.com` tarball straight into memory (60 MB cap, 400-file cap), keeps only
Python/TS/JS source under 200 KB per file, and then builds a **Code Property Graph** out of it
using tree-sitter — classes, methods, functions, imports, and *scoped* call sites. That graph is
the product. From it, deterministically and with zero LLM calls, ArchiMind derives an HLD, an
LLD, a call-flow sequence diagram, a chapter handbook, three Clean-Architecture invariants, a
blast-radius tracer, and an onboarding challenge mined from untested seams. An LLM (Gemini) is
*optional garnish* on top: it can rewrite the handbook prose and redraw the diagrams, but every
LLM output passes through a Mermaid validator and, if it fails, is discarded in favour of the
deterministic graph-derived diagram. Three real open-source codebases (PyTorch, OpenClaw,
Requests) are pre-baked into JSON fixtures so the demo works with zero network and zero compute.

---

## 2. The Shape of the System

```
                      ┌──────────────────────────────────────────┐
  browser  ──POST──▶  │  app.py   Flask :5000                   │
                      │   · route table (10 routes)             │
                      │   · auth + rate limits + CSP headers    │
                      │   · spawns worker.py as a subprocess    │
                      └───┬───────────────┬──────────────────────┘
                          │               │ inline (no subprocess)
       subprocess.Popen   │               ▼
                          │        ┌──────────────────────────────────────┐
                          ▼        │ src/*  (imported on demand)         │
                 ┌──────────────┐  │  cpg / governance / orchestration  │
                 │ worker.py    │  │  agentic / security / storage      │
                 │  8 stages    │──┤  config (pydantic + constants)     │
                 │  progress %  │  │  ingestion (tarball/subtree)       │
                 └──────┬───────┘  └──────────────────────────────────────┘
                        │
      ┌─────────────────┼──────────────────┬────────────────────┐
      ▼                 ▼                  ▼                    ▼
 services.py       data/status.json    SQLAlchemy DB      src/storage/
 (repo+vector+doc)  (per-analysis)      (users, logs,      golden_fixtures/
                                        history)          *.json
```

Two engines coexist, deliberately:

| | **Legacy retrieval engine** | **v2 CPG engine** |
|---|---|---|
| Lives in | `services.py` (2418 lines) | `src/` (21 modules) |
| Index | Vector store, 2 tiers (summaries + AST chunks) | NetworkX `DiGraph` of symbols |
| Non-determinism | Gemini embeddings + Gemini prose | None; everything from the graph |
| Used for | `/api/chat` context, handbook fallback | Chat tools, blast radius, invariants, challenge, all fallback diagrams |
| Backend picks | Pinecone / ChromaDB / `_SimpleCollection` JSON | Pure CPU |

The worker runs **both**. It builds the vector index for context, *then* prepends the CPG
summary to that context, and finally uses the CPG diagrams as the guaranteed-valid fallback if
Gemini's Mermaid fails validation.

---

## 3. The Request Lifecycle, End to End

### 3.1 `POST /api/analyze`

```
app.py:_api_analyze
 ├─ payload.get("repo_url")                  → 400 if empty
 ├─ _is_valid_repository_url                 → 400 unless it matches the GitHub regex
 ├─ _resolve_actor_context()                 → {user_id | session_id}
 ├─ anonymous && count >= 5                  → 403 {limit_reached: true}
 ├─ running = AnalysisLog(status IN pending,processing).count()
 │    && running >= SETTINGS.max_concurrent_jobs (1)  → 429 {retry: true}
 ├─ INSERT AnalysisLog(status='pending')      → gets .id
 └─ subprocess.Popen([sys.executable, "worker.py", repo_url, str(id)])
      returns 202 {analysis_id, status_url, doc_url, repo_name}
```

### 3.2 The worker, stage by stage

`worker.py:AnalysisWorker.run_analysis` writes `data/status_<id>.json` (and mirrors to
`data/status.json`) at every stage, so `/api/status` can be polled.

| Stage | Progress | What happens |
|---|---|---|
| `queued` | 0 | status skeleton written |
| `preparing` | 8 | derive repo name + collection name, pick clone path |
| `ingestion` | 22 | tarball → remote API → local clone (first success wins) |
| `indexing` | 46 | `vector_service.reset()` then `generate_embeddings(files)` |
| `retrieval` | 64 | `query_similar_documents("Generate a complete technical documentation…")` |
| `graph` | 72 | `build_graph()` → CPG → cpg_context_block + 3 deterministic diagrams + invariants → `to_compact` |
| `generation` | 82 | `generate_all_documentation()` + evaluator-optimizer repair loop per diagram |
| `completed` | 100 | status result assembled, DB updated, history saved |

On any exception: `status="error"`, the exception string goes in `error`, DB gets `"failed"`.

### 3.3 Ingestion, in order

```
_collect_with_tarball_first()
 ├─ src/ingestion/_00_tarball_client.stream_files()     ← 64 KB chunked codeload stream
 │    └─ src/ingestion/_01_file_filter.keep_member()     ← ext + dir + size gate
 │    └─ src/ingestion/_01_file_filter.decode_sources()  ← basename-keyed, 400 cap
 └─ (on any exception) services.RepositoryService.collect_repository_files()
      ├─ _fetch_remote_repository_files()   ← GitHub trees API + raw.githubusercontent, scored
      └─ clone_repository() + read_repository_files()   ← GitPython depth=1
```

### 3.4 The CPG build, precisely

`src/cpg/_00_ts_ast.py` → per file, a `ModuleSymbols`:
`classes{cls→bases}`, `functions[]`, `methods{cls→[names]}`, `imports{local→module}`,
`calls[]`, `scoped_calls[(scope, leaf, receiver)]`, `parse_ok`.

`src/cpg/_01_cpg_builder.py` → a `networkx.DiGraph` with node kinds `File | Class | Function |
External` and edge kinds `DEFINES | CALLS | INSTANTIATES | INHERITS | IMPORTS`.

Resolution ladder for a call (this is the interesting part):
1. `self`/`this`/`cls` receiver + method of the owning class → bind to *that* class only.
2. Name matches a known class → `INSTANTIATES`, not `CALLS`.
3. Same-file target wins.
4. Else if the name or receiver is imported → narrow candidates to files whose stem matches an import.
5. If more than 3 candidates remain → **drop the edge** (`MAX_AMBIGUOUS`).

Node IDs are structural: `f::path`, `c::path::Class`, `fn::path::func`, `m::path::Class::method`,
`ext::Name`.

### 3.5 Chat, with tool routing

`app.py:_api_chat` does keyword routing over the question text (no LLM tool-calling loop):

| Question contains | Tool called |
|---|---|
| `impact blast affect break depend change caller who uses` + a known symbol | `trace_symbol_impact` |
| `invariant rule layer cycle clean architecture violat` | `verify_architecture_rules` |
| a known symbol, and no other tool fired | `get_symbol_ast` |

Tool JSON is prepended to the context as `TOOL <name>(<arg>) -> <json>` so Gemini can narrate
over real data. If Gemini throws, the response degrades to the raw tool summaries rather than
losing the deterministic result.

---

## 4. Root Files

### `00_main.py` — 13 lines
Production entrypoint in the repo's numeric-prefix directive layout. Imports `create_app` from
`app.py`, instantiates it at module scope (`app = create_app()`), and only calls `app.run()` under
`__main__` on `0.0.0.0:$FLASK_PORT`. Its whole job is to exist so gunicorn/Docker/scripts can use
`00_main:app` while `app:create_app()` keeps working.

### `app.py` — 643 lines — the HTTP surface
The largest hand-written file after `services.py`. Structure:

| Symbol | Role |
|---|---|
| `_get_bool_env`, `_build_csp_header` | env parsing; CSP directive map (script-src allows jsdelivr + inline, frame-ancestors `'none'`) |
| `class ApplicationConfig` | pulls `SECRET_KEY`, `DATA_PATH`, `DATABASE_URL`, cookie hardening (`HTTPONLY`, `SAMESITE=Lax`, `SECURE` auto-off when `FLASK_DEBUG`), `MAX_CONTENT_LENGTH = 2 MB` |
| `class ArchiMindApplication` | the app object |
| `REPOSITORY_URL_PATTERN` | strict regex: only `https://github.com/o/r(.git)?` or `git@github.com:o/r(.git)?` |
| `__init__` | ProxyFix(x_for/proto/host/port=1) → ApplicationConfig → RepositoryService → data dir → config → extensions → security hooks → routes |
| `_configure_application` | SQLite gets `check_same_thread: False`; Postgres gets `pool_pre_ping` + `pool_recycle=300` |
| `_initialize_extensions` | `db.init_app`, `init_oauth`, registers `oauth_bp`, `init_redis()` no-op, LoginManager + `user_loader`, `db.create_all()` |
| `_register_security_hooks` | `after_request` adding `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, CSP, and HSTS when cookies are secure |
| `_status_file_for_analysis(id)` | `data/status_<id>.json` |
| `_resolve_actor_context` | authenticated → `user_id`; anonymous → mints and stores a UUID `session_id` |
| `_is_valid_repository_url` | length ≤ 400 + regex |
| `_load_cpg_artifact` | golden fixture **or** `status_<id>.json`; `int()` coercion blocks path traversal |
| `create_app()` / `if __main__` | WSGI factory and `debug=True` dev run |

Routes:

| Route | Methods | Behaviour |
|---|---|---|
| `/` | GET | `01_landing.html` |
| `/workspace`, `/workspace/<ref>` | GET | `02_studio.html`; `ref` is `golden:pytorch` or an analysis id |
| `/doc` | GET | `doc.html` from `status_<id>.json` (404 unless `status == "completed"`) |
| `/api/analyze` | POST | 202 / 400 / 403 / 429, spawns worker |
| `/api/status` | GET | owner-scoped; **falls back to a shared completed payload** for non-owners (public-repo results are shareable, in-flight work is not) |
| `/api/check-limit` | GET | `{can_generate, count, limit, authenticated}` |
| `/api/preview` | GET | GitHub repo metadata card |
| `/api/chat` | POST | guardrail → 5-question anon quota → CPG tool routing → vector context → Gemini answer → scrub. Returns `{answer, engine, tools_used}`. On Gemini failure returns tool summaries. |
| `/api/challenge` | GET | `?golden=` or `?analysis_id=`, `?n=` index |
| `/api/golden`, `/api/golden/<id>` | GET | demo list (light) / demo detail (no CPG) |
| `/api/blast-radius` | GET | `?symbol=` required (400), graph required (404) |
| `/api/history`, `/api/history/<id>` | GET | `login_required` |
| `/login` `/logout` `/sign-up` | GET/POST | classic email+password, `pbkdf2:sha256`, `remember=True` |

Notable: `_api_chat` clamps questions to 250 chars, and `sign_up` validates email ≥ 4, first name
≥ 2, password ≥ 7, match.

### `config.py` — 108 lines — legacy runtime config
Plain module-level `os.getenv` (no pydantic). Key exports:
`DATA_PATH=./data`, `LOCAL_CLONE_PATH=data/temp_repo`, `VECTOR_STORE_PATH`/`CHROMA_DB_PATH=
data/vector_store`, `SQLITE_URL`, `STATUS_FILE_PATH`.
`_normalize_database_url` is the interesting branch: schemeless values (a bare token, a path)
fall back to SQLite; `postgres://` and `postgresql://` are rewritten to `postgresql+psycopg://`;
relative `sqlite:///x` is made absolute. Then Gemini models, `VECTOR_BACKEND` (auto-`pinecone`
if `PINECONE_API_KEY` present), Pinecone coordinates, `REMOTE_FETCH_*` limits, and
`ALLOWED_EXTENSIONS` / `IGNORED_DIRECTORIES` for the legacy scanner.

### `models.py` — 109 lines — SQLAlchemy schema
`db = SQLAlchemy()` is created here and imported everywhere else.

- **`User`** (table `users`) — `email` unique+indexed, nullable `password` (OAuth users have none),
  `oauth_provider`, `oauth_id` unique, `created_at`. Relationships `analyses` and
  `repository_history` both `cascade='all, delete-orphan'`. Helpers `get_analysis_count()`,
  `get_recent_repositories(limit=5)`.
- **`AnalysisLog`** (`analysis_logs`) — `user_id` FK nullable, `session_id` for anonymous quota,
  `repo_url`, `status`, `created_at`, `completed_at`. This single table is both the audit log
  *and* the rate limiter *and* the concurrency guard.
- **`RepositoryHistory`** (`repository_history`) — full artifacts as TEXT: `documentation`,
  `hld_graph`, `lld_graph`, `chat_summary`; `last_accessed` with `onupdate=now()`.
  `add_or_update` is the classmethod that keeps **only the 5 most recent repos per user** by
  deleting the oldest by `last_accessed`.

### `auth.py` — 115 lines — **dead code**
A complete `auth` Blueprint (`/login`, `/logout`, `/sign-up`, `/api/check-limit`) that duplicates
`app.py` handlers. Nothing imports it; `app.py` registers its own routes on the main app. Left over
from the pre-`app.py`-owns-routes layout. Note it also references `url_for('index')`, an endpoint
that no longer exists — instant `BuildError` if it were ever registered.

### `oauth_utils.py` — 204 lines — Google OAuth + history cache
- `oauth = OAuth()`, `oauth_bp` Blueprint with `/login/google` and `/login/google/callback`.
- `init_oauth(app)` registers Google with `server_metadata_url` (no hardcoded endpoints) and
  scope `openid email profile`.
- `google_callback` handles three cases: existing by `oauth_id`; existing by email → *link* the
  OAuth identity onto the password account; otherwise create a user with `password=None`.
- `init_redis()` is a **no-op kept for backward compatibility** — the cache is a plain dict.
- Cache API: `get_cached_history` / `set_cached_history(user_id, data, expiry=3600)` (the `expiry`
  arg is accepted and `del`'d) / `invalidate_history_cache`, keyed `user:{id}:history`.
- `get_user_repository_history(user_id, use_cache=True)` → list of `{id, repo_name, repo_url,
  last_accessed, has_documentation, has_hld, has_lld}`.
- `save_repository_to_history` JSON-ifies dict graphs then calls `add_or_update` and invalidates.
- `get_repository_details(user_id, repo_id)` → full artifacts with graphs `json.loads`'d back,
  scoped by `user_id` so one user cannot read another's history.

### `services.py` — 2418 lines — the legacy service layer
Six top-level pieces:

**`ConfigurationError`** — raised when a backend is requested but its package is missing.

**`@dataclass ChunkRecord`** (`chunk_id`, `text`, `metadata`) and
**`@dataclass RetrievedContextFile`** (`file_path`, `language`, `function_name`, `github_url`,
`content`) — the two shapes that flow between indexing, retrieval, and doc synthesis.

**`class RepositoryService`** — a `__new__` singleton (`_instance`/`_initialized` guard).
- `clone_repository(url, path)` — returns `True` if the path already exists (reuse), else
  `git.Repo.clone_from(depth=1, single_branch=True)`.
- `_parse_github_repo` / `build_collection_name` — both regex `github.com[:/](owner)/(repo)`;
  the latter yields `owner__repo` lowercased (this is why the test expects `exampleorg__myrepo`).
- `_http_get_bytes` — 3 attempts, linear backoff `min(2.0, 0.35·attempt)`, retries only
  `{408,409,425,429,500,502,503,504}` + transport errors. **Key behaviour: on `IncompleteRead` with
  a `max_bytes` bound it returns the partial payload immediately** — a truncated README is better
  than none.
- `_http_get_json` — retries on truncated JSON (same partial-read recovery).
- `_is_allowed_file`, `_score_path_priority` — a hand-tuned importance score:
  README +200, `docs/` +130, architecture/design/diagram/hld/lld +120, docker/requirements/pyproject
  +100, `app|main|server|api|service|worker|model|controller` +80, `.md` +30, shallow path +20.
- `_select_remote_paths` — filters blobs by extension/size, and if over `REMOTE_FETCH_MAX_FILES`
  (120) sorts by priority desc then size asc and truncates.
- `_fetch_remote_repository_files` — repo meta → default branch → `git/trees/<branch>?recursive=1`
  → parallel `raw.githubusercontent.com` fetch in a `ThreadPoolExecutor` (8 workers) → synthesises
  a `__repo_overview__.md` pseudo-file carrying description/language/stars/issues/topics/whether
  GitHub truncated the tree. That pseudo-file is what the doc synthesizer later reads for
  "purpose".
- `get_repository_preview` — the `/api/preview` card payload.
- `collect_repository_files` — remote first, local clone as fallback.
- `read_repository_files` — `os.walk` with `dirs[:]` pruning, relative paths as keys.

**`class _SimpleCollection`** — a ~100-line JSON-file vector collection used when neither
ChromaDB nor Pinecone is configured. Chroma-shaped API (`add`/`query`/`count`/`clear`). Scoring is
cosine over stored embeddings if present, else a `hits/len(tokens)` keyword ratio. Supports a
`where={"file_path": ...}` filter. This is what `VECTOR_BACKEND=local` and every test uses.

**`class _PineconeCollection`** — real Pinecone wrapper: `_ensure_index` creates a serverless
index if absent (handles both the `list_indexes().names()` object API and a list/dict API),
namespaces are `{namespace}:{collection}:summaries|chunks`, `add` upserts in batches of 100,
the document text rides inside `metadata["document"]` and is popped back out on query, `clear`
tries both `delete_all` kwarg orders.

**`class VectorStoreService`** — the hierarchical index.
- Constructor derives two collection names: `<repo>` `_summaries` and `<repo>` `_chunks`,
  sanitising `-./` to `_`. `_initialize_database` picks Pinecone → ChromaDB → SimpleJSON and
  wraps any failure in `ConfigurationError`.
- `_normalize_embedding` — truncate/pad to `PINECONE_DIMENSION` then L2-normalise.
- `_hash_embed_text` — a *deterministic* local embedding: SHA-256 each token, 4 signed
  projections into the vector, weight by token length. No API key, no network, stable across runs.
- `_embed_texts` — Gemini `embed_content` if the model name starts with `models/` and a key
  exists, else silently falls back to the hash embedder.
- Chunking ladder in `_make_chunk_records`: Python `ast` top-level defs/classes → LlamaIndex
  `CodeSplitter(chunk_lines=120, overlap=20, max_chars=3200)` → 80-line sliding window. Every chunk
  gets `file_path`, `language`, `function_name`, `github_url`, `start_line`, `end_line` and a
  16-hex-char `sha256(path:start:index)` id.
- `_build_summary` — heuristic one-liner: first non-comment line + regex counts of classes,
  functions, imports.
- `generate_embeddings` — writes the summary tier and the chunk tier.
- `query_similar_documents` — the 3-node LangGraph: `select_files` (top 8 summary hits → candidate
  file paths) → `collect_chunks` (per-file `where` filter on the top 5 candidates, budget
  divided by count; falls back to an unfiltered query if no candidates) → `render_context`
  (emits `--- File: … ---` blocks with `language=`, `function_name=`, `github_url=` headers).
  If LangGraph is missing or the graph raises, it calls the same three functions inline.

**`class DocumentationService`** — 1250 lines, the most layered class here.
- `CONTEXT_BLOCK_PATTERN` — the inverse of `render_context`, used to re-parse the context string.
- `GRAPH_RESPONSE_SCHEMA` — `{title, description, mermaid_code}`, required, for Gemini structured output.
- `_can_use_gemini` / `describe_backend` — `gemini:<model>` or `local`.
- `_clip_context` — truncate on a newline boundary at `DOCUMENTATION_CONTEXT_CHAR_LIMIT` (36000).
- `_generate_with_gemini` — `ThinkingConfig(thinking_level=…)`, `HttpOptions(api_version=…)`,
  logs elapsed time, and `_response_to_text` falls back to joining `response.parts`.
- Five prompt builders: `_documentation_prompt` (9 required chapters), `_graph_prompt`
  (hld / flow / lld variants, "return JSON matching the schema, no code fences"),
  `_chat_summary_prompt` (8–10 sentences), `_chat_answer_prompt` (direct answer, then reasoning,
  cite file paths, say so when context is incomplete).
- **The local heuristic profiler** — this is a self-contained mini static analyzer:
  `_parse_context_records`, `_extract_overview` (parses `__repo_overview__.md`),
  `_readme_excerpt` (skips headings containing setup/install/running/usage, strips code fences and
  badges, prefers paragraphs matching `is|allows|helps|provides|converts|generates` that are *not*
  install instructions), `_infer_stack` (15 markers: Flask, FastAPI, Django, SQLAlchemy,
  PostgreSQL, SQLite, Jinja, Docker, Gunicorn, Pandas, NumPy, Requests, Click, LangGraph,
  Pinecone), `_infer_repo_type` (web app / CLI tool / library / project), `_find_entry_points`
  (9 preferred filenames + `Flask(`/`@app.route`/`def main(` patterns), `_score_component` +
  `_infer_component_role` (role strings like "HTTP entry point and route handling"), top 6,
  `_infer_data_stores`, `_infer_integrations`, `_infer_deployment_clues`, `_build_flow_steps`.
- `_build_repository_profile` — assembles all of the above plus `tests_present` and
  `advanced_pipeline_present` (looks for langgraph/celery/rq/dramatiq/pinecone/chroma/vector store).
- Local generators: `_build_local_summary` (careful "X appears to be a …" article/verb grammar),
  `_build_local_documentation` (9-chapter markdown, including an explicit *"treat any earlier claim
  of that architecture as incorrect"* line when no pipeline was seen), `_build_local_hld`
  (flowchart TD, caller→entry→components→presentation→output with dashed state/external edges),
  `_build_local_lld` (sequenceDiagram with participants), `_build_local_flow` (flowchart LR),
  all wrapped by `_graph_payload` into the same JSON shape Gemini returns.
- `_question_tokens` (with a 22-word stopword list), `_select_relevant_files_for_question`,
  `_build_local_chat_answer` ("Direct answer:" then "Reasoning:" then "Relevant files:").
- Public entry points: `generate_all_documentation` (Gemini all-or-nothing, falling back to the
  local set on any exception), `generate_chat_answer` (Gemini → local), `generate_chat_summary`
  and `generate_documentation` (local only — note these two never call Gemini, which is why
  `test_documentation_service_generate_all` sees 5 `generate_content` calls and nothing else).

### `worker.py` — 525 lines — the background pipeline
Prepends `PROJECT_ROOT` to `sys.path` so the subprocess resolves `src/`. Imports heavy modules at
top level (`config`, `services`) but defers every `src/*` import into the function that needs it —
cheap process startup.

- `_update_status` — writes the per-analysis file **and** mirrors it to `status.json`.
- `_set_stage(stage, message, progress, path)` — the progress reporter.
- `_collect_with_tarball_first` — tarball, else the `services` fallback.
- `_generate_with_repair` — the evaluator-optimizer driver: generate all docs, and for each of
  `hld/lld/flow`, if the diagram does not validate, call `run_eval_optimizer` with a regeneration
  lambda that injects the validator's error text into the prompt. Returns `(docs, repair_log)`
  where `repair_log[kind]` is the attempt count.
- `_regen_diagram` — one regeneration attempt, JSON-cleaned and normalized.
- `_update_database_log` — spins up a throwaway `create_app()` to write status transitions.
  (Costly but correct: reuses the app factory instead of duplicating engine config.)
- `_clean_json_response` — strips ```` ```json ```` fences, then slices from the first `{` to the
  last `}`.
- `_sanitize_mermaid_code` — three LLM-output repairs: collapse newlines inside `[...]` labels,
  rename snake/kebab node ids to camelCase (longest-first to avoid partial replacement, prefixing
  a leading digit with `node`), and drop stray single letters between nodes (`] A -->`). Also
  strips `activate`/`deactivate` lines.
- `_parse_graph_data` — clean → JSON → normalize + sanitize `mermaid_code` → `{status, graph}` or
  `{status: "error", message, raw_preview[:400]}`.
- `_save_to_history` — only when the `AnalysisLog` has a `user_id`; anonymous results are not stored.
- `run_analysis` — the 8-stage flow. Two details worth calling out:
  1. **The CPG step is best-effort.** Wrapped in `try/except` that logs "CPG grounding skipped" and
     continues with an empty artifact.
  2. **The diagram fallback ladder**: if the parsed LLM diagram is missing *or* fails
     `validate_mermaid`, replace it wholesale with the CPG-derived diagram and set
     `repair_log[kind] = 0`. The canvas can therefore never be blank or show a syntax error.
  It also caps the serialized artifact at 5000 nodes (`subgraph(...).copy()`) while analysing the
  full graph.
- `main()` — CLI: `python worker.py <repo_url> [analysis_log_id]`.

### `Dockerfile` — multi-stage
Stage 1 `builder` on `python:3.11-slim`: apt `build-essential python3-dev`, creates `/opt/venv`,
installs `requirements.txt` only. Stage 2 is the runtime: copies the venv, `apt install git
ca-certificates`, creates a non-root `archimind` user, `mkdir /app/data` chowned, `EXPOSE 5000`, a
`HEALTHCHECK` that curls `/api/status`, and a `CMD` running gunicorn against `app:create_app()` with
`--workers ${GUNICORN_WORKERS:-1} --threads 4 --timeout 240`. Test/lint tooling never enters the
image.

### `docker-compose.yml` — local/Render compose
Builds or pulls `${ARCHIMIND_IMAGE:-archimind:latest}`, `env_file: .env`, port `80:5000`, named
volume `archimind_data:/app/data`, gunicorn with **2 workers** (note: differs from the Dockerfile's
1-worker default, because the measured memory budget in `docs/profiling.md` is for 1×4), same
healthcheck.

### `docker-compose.pi.yml` — the Pi compose
Identical minus the `build:` block (the Pi only pulls), with `FLASK_HOST/PORT/DEBUG` pinned and
defaulting to `krishnah27/archimind:latest`. This is the file `deploy_pi.sh` copies to the Pi as
`docker-compose.yml`.

### `requirements.txt` — runtime pins
Flask 3.1.3, Flask-Login, Flask-SQLAlchemy, Authlib, SQLAlchemy 2.0.48 + `psycopg[binary]`,
`google-genai==1.69.0`, `llama-index-core`, `langgraph==0.2.70`, `pinecone>=5,<8`,
`tree-sitter` + `tree-sitter-python`, `networkx==3.4.2`, `pydantic` + `pydantic-settings`,
GitPython, python-dotenv, gunicorn.
**`tree-sitter-typescript` is not listed** — `src/cpg/_00_ts_ast.py` therefore falls back to the
stdlib `ast` path for `.ts`/`.js` files in a clean install, and the TS unit test only passes where
the grammar happens to be installed.

### `requirements-dev.txt` — `-r requirements.txt` plus pytest 7.4.3, pytest-cov, pytest-mock,
black 23.12.1, flake8, isort, bandit. Kept out of the container.

### `pyproject.toml` — three tool configs
ruff (py310, line 110, rules `E9,F63,F7,F82,F541,F841,I`), black (line 110, py310), mypy
(`strict = true`, py310, `disallow_untyped_defs` for `services/app/worker/models/auth/oauth_utils`).

### `.env.example` — 100 lines, the annotated config surface
Opens with an `# AGENT INSTRUCTION:` block (SRP, standardized logging, never hardcode secrets).
Documents `SECRET_KEY`, Gemini model/version/thinking vars, the three vector backends with a
comment that the *current* Pinecone index is 1024-dim (note `config.py`'s default is 768 — a real
divergence you must fix by setting the env var), the Supabase pooler `DATABASE_URL` recipe with
URL-encoding guidance, Flask runtime, `ANONYMOUS_GENERATION_LIMIT`, `MAX_CONCURRENT_JOBS=1`,
`MERMAID_MAX_RETRIES=3`, tarball bounds, OAuth, and the Pi/Docker defaults (`ARCHIMIND_IMAGE`,
`DOCKERHUB_REPO`, `PI_USER/HOST/DIR`), and `OAUTHLIB_INSECURE_TRANSPORT=0` for production.

### `.coveragerc` — coverage source `.`, omits tests/venv/site-packages/migrations; excludes
`pragma: no cover`, `__repr__`, `NotImplementedError`, `__main__`, `TYPE_CHECKING`, `@abstractmethod`.
Note it does **not** omit `src/`, so engine code counts toward coverage.

### `.gitignore` / `.dockerignore`
`.gitignore` covers env/secrets, Python, venvs, IDE, OS, logs, temp, `*.db`/`*.sqlite`,
`neo4j/`, `data/`, `logs/`, coverage, pytest, Jupyter, pyenv, pipenv, PEP 582, celery, `.sage.py`,
Spyder/Rope, mkdocs `/site`, mypy and pyre caches.
`.dockerignore` is the tighter subset so the build context excludes `.env`, `.git`, `/data/`,
`/tmp/`, coverage and pytest artifacts.

### `README.md` — 437 lines
Landing-page doc: capability list, a Mermaid block diagram, ingestion/hierarchical-index/query
explanations, quick start, env var tables, run modes, API reference, four use cases, project
structure, quality/security, troubleshooting (SQLite open errors, 403 limits, weak retrieval, local
OAuth), and DOT diagram inventory. See [§13](#13-where-the-readme-lies) for what it no longer
describes.

### `setup.sh` — 4 useful lines
Root convenience wrapper: `cd`s to its own directory and delegates to `scripts/setup_local.sh`.

### `opencode.json`
Disables the `composio` MCP server. Agent tooling config, not app config.

### `.autoresearch-stop`
Empty marker file used by the autoresearch loop to signal a stop.

---

## 5. `src/` — The Engine

`src/__init__.py` holds a single docstring: *"ArchiMind production engine: deterministic CPG +
agentic orchestration + governance."* All eight subpackage `__init__.py` files are empty. Numeric
filename prefixes (`_00`, `_01`, …) establish intra-package load order.

### 5.1 `src/config/` — the typed config branch

**`_00_settings.py`** — a Pydantic v2 `BaseSettings` named `Settings`, `env_file=".env"`,
`extra="ignore"`, every field aliased to its SCREAMING_SNAKE env var:

| Field | Default | Meaning |
|---|---|---|
| `gemini_api_key` | `""` | API key |
| `documentation_model` / `chat_model` | `gemini-3.1-flash-lite-preview` | model ids |
| `embedding_model` | `models/gemini-embedding-001` | embedding model |
| `max_concurrent_jobs` | `1` | the 429 guard in `_api_analyze` |
| `data_path` | `data` | data root |
| `golden_cache_path` | `data/golden` | declared but unused at runtime |
| `tarball_max_mb` | `60` | stream cap |
| `tarball_max_files` | `400` | decode cap |
| `tarball_timeout_s` | `60` | socket timeout |
| `mermaid_max_retries` | `3` | evaluator-optimizer ceiling |

A module-level `SETTINGS = Settings()` is the single shared instance (with a `ponytail:` note that
env is read once at import).

**`_01_constants.py`** — frozen, dependency-free constants shared across the engine:
`ALLOWED_EXTENSIONS` (`.py .js .ts .tsx .jsx .mjs`), `CPG_EXTENSIONS` (the CPG subset),
`IGNORED_DIRECTORIES` (includes `tests`, `docs`, `examples`, `vendor` — the CPG ignores tests on
purpose, which is what makes "zero callers" a meaningful untested-seam signal),
`SKIP_SUFFIXES` (binaries), `MAX_FILE_BYTES = 200_000`, `DUNDER_EXEMPT_BASE = "object"`, the three
invariant id strings, and `GOLDEN_REPOS` — a 3-tuple table
`(id, title, subtitle, owner/repo, subtree_dirs)` for pytorch/openclaw/requests.

### 5.2 `src/ingestion/` — getting code in, cheaply

**`_00_tarball_client.py`**
`repo_tarball_url(url, ref="HEAD")` — validates that the 3rd path segment contains `github.com`,
else `ValueError`, then builds `https://codeload.github.com/{owner}/{repo}/tar.gz/{ref}`.
`stream_files` — requests with a `User-Agent`, reads **64 KB chunks into a `BytesIO`** and aborts
with `RuntimeError` past `tarball_max_mb` (so a 4 GB monorepo never fills RAM), then opens it with
`tarfile.open(mode="r|gz")` (streaming, not seekable) and keeps only members passing
`keep_member`. Returns `{arcname: bytes}` plus meta `{url, files, skipped, bytes}`.

**`_01_file_filter.py`**
`keep_member(arcname, size)` — rejects over `MAX_FILE_BYTES`, any path component in
`IGNORED_DIRECTORIES`, any `SKIP_SUFFIXES` tail, and anything whose extension is not in
`ALLOWED_EXTENSIONS`. Note this rejects `.md` — the CPG branch is source-only.
`decode_sources(raw, max_files)` — sorts by arcname, **keys by basename only** (first wins, so
`a/x.py` and `b/x.py` collide — the test acknowledges this), decodes with `errors="replace"`, stops
at the cap.

**`_02_subtree_client.py`**
Built for `pytorch/pytorch`, whose tarball blows the 60 MB cap. `_get` adds
`Authorization: Bearer $GITHUB_TOKEN` for `api.github.com` when the token is set.
`fetch_subtree(repo, dirs, per_dir=30, total=80)` — lists each directory through the contents API,
skips non-files, test-ish names (`.test`, `.spec`, `test-support`, `test-utils`), and `.d.ts`, then
streams `download_url` raws. This is the offline builder for the golden fixtures.

### 5.3 `src/cpg/` — the graph

**`_00_ts_ast.py`** — the extractor. `ModuleSymbols` dataclass; a `_SPEC` table of tree-sitter node
type names per language (python vs typescript, differing in class/function/call/member node names
and in which field holds the callee). `_parser(lang, path)` lazily imports
`tree_sitter` + `tree_sitter_python` or `tree_sitter_typescript`, picking the TSX grammar for
`.tsx`/`.jsx`. `_imports` is regex-based per language. `_extract_treesitter` walks an explicit stack
of `(node, class_name, scope_name)`; on a class it records bases (python: the `superclasses` field;
TS: `extends` in `class_heritage`) and seeds `methods`; on a function it decides method vs module
function from the *current* scope; on a call it splits the callee into leaf + receiver, skips
non-identifiers and the `_JS_KEYWORDS` set, and records `(scope, leaf, receiver)`. It also treats a
`variable_declarator` holding an arrow/function expression as a function, which is how TS callbacks
get a scope. `parse_ok = not tree.root_node.has_error`. `_extract_ast` is the stdlib fallback for
Python (walks `ast`, records bases/classes/functions/`ast.Call` leaves and receivers) and sets
`parse_ok=False` on `SyntaxError`. `extract_module` tries tree-sitter first, falls back to `ast`.

**`_01_cpg_builder.py`** — the graph. Node kind constants (`File/Class/Function`), edge kind
constants, `IMPACT_EDGES = {CALLS, INSTANTIATES, INHERITS}` (the edges that propagate impact),
`MAX_AMBIGUOUS = 3`. Helpers `_qid` (`::`-joined ids), `_stem`, `_import_stem` (handles both
`./foo.js` and `a.b.c`), `_scope_node` (maps a scope string to a node id, including the
module-level pseudo-scope `f::path`).
`build_graph(files)` — pass 1 creates every node and every `DEFINES` edge and indexes
`classes{cls→[ids]}` / `funcs{name→[ids]}`; pass 2 adds `INHERITS` (unresolvable bases become
`ext::Name` `External` nodes) and then resolves every scoped call through the ladder described in
[§3.4](#34-the-cpg-build-precisely). `_roots` (exact name, then leaf-name match) and
`blast_radius` (iterative reverse BFS over `IMPACT_EDGES`, excluding the roots themselves).
`out_of_corpus_bases` (class → bases with no in-corpus class, skipping `object`).
`to_compact` / `from_compact` — the JSON round-trip: `{nodes:[{id,kind,name,path}],
edges:[{src,dst,kind}]}`. This is what lands in `status.json`, the golden fixtures, and every API
response.

**`_02_closure_gate.py`** — soundness guard for "dead code" claims. `withheld_methods(g)` returns
every method node whose owning class inherits from a base with no in-corpus definition, with the
reason string. The docstring states the reasoning: such a class participates in a protocol owned by
unanalyzed code, which may dispatch to a method name that does not appear in the corpus. The gate
is one-directional — it can only *remove* certificates, never create them. `certified_dead`
filters a predicted-dead list through it. No hand-curated allowlists; it is computed.

### 5.4 `src/governance/` — the policy branch

**`_00_blast_radius.py`** — `impact(symbol, artifact)` — the API-shaped wrapper: rebuild the graph
from a compact artifact, BFS, dedupe names, and return `{symbol, impacted[], edges, ms}`. Timing is
measured and returned because the UI shows it.

**`_01_invariants.py`** — three structural Clean-Architecture rules, evaluated on edges only
(`IMPORTS`, `CALLS`):
1. `presentation-isolation` — no direct edge from a presentation-layer file
   (`route|view|present|api|handler|controller` in the path) to a data-layer file
   (`repo|dao|store|db|model|entity|schema`).
2. `acyclic-dependencies` — `nx.find_cycle` over the whole graph; no cycle passes.
3. `domain-purity` — no edge from a domain-layer file (`service|usecase|use_case|domain|core`) to
   anything under `infra|external|third`.
`layer_of` is a substring classifier, so these are heuristics by construction — the detail lists are
capped at 20 and each result is `{id, passed, details}`.

### 5.5 `src/orchestration/` — the generation branch

**`_00_agent_state.py`** — a 14-line `DiagramState(TypedDict, total=False)` with
`kind, repo_name, context, mermaid, validation_error, attempts, history`. This is the LangGraph
state schema; `total=False` makes every field optional so partial updates are legal.

**`_01_eval_optimizer.py`** — the self-healing loop, and the most carefully-reasoned module in the
repo. `normalize_mermaid` does three things: unescape literal `\n`/`\r\n` (double-encoded JSON
payloads), and — only when the header is `graph `/`flowchart ` — entity-encode parens inside `[...]`
labels (`(`→`#40;`, `)`→`#41;`) and quote bare `subgraph Id [Words]` titles. `validate_mermaid`
returns `""` for valid, else a short machine-readable error, checking: empty; escaped-newline
payloads (with the note *"needs unescaping, not reflection"* — reflection cannot fix it);
header must be one of graph/flowchart/sequenceDiagram/classDiagram/stateDiagram; balanced `[`/`]`;
balanced `(`/`)`. For flowcharts specifically, any paren inside a `[...]` label is rejected. A
`_MERMAID_BAD` regex catches code fences, `<script`, `{{`/`}}`, doubled brackets, and stray `#`
(not a numeric or hex entity). Node factories `_generate_node` / `_validate_node` /
`_reflect_node` and a `_route` conditional that ends when there is no error or when
`attempts >= MERMAID_MAX_RETRIES`. `run_eval_optimizer` builds a `StateGraph`; when a
`first_draft` is supplied the entry point is `validate` (skip the redundant first generation);
otherwise `generate`. If LangGraph is unimportable it falls back to a single shot. The returned
state is rebuilt field-by-field with `str()`/`int()` coercion, which is how `test_eval_optimizer_heals_broken_mermaid`
can assert `attempts == 2`.

**`_02_doc_synthesizer.py`** — `cpg_context_block(g, char_limit=6000)` produces the deterministic
architecture summary prepended to every prompt: sorted file list (first 60), sorted class list
(first 80), a function count, and up to 200 `name -[KIND]-> name` architecture edges, truncated to
6000 chars. `synthesize(context, repo_name, graph, fn)` is the one-liner that prepends it and
delegates. (`worker.py` inlines the same concatenation instead of calling `synthesize`.)

**`_03_cpg_diagrams.py`** — valid-by-construction Mermaid, used for golden demos and as the
fallback. Sanitizers first: `_sid` (identifier-safe, 40 chars, prefixed `n`), `_label` (strips every
Mermaid-hostile character, 34 chars), `_group` (last 2–3 path segments → package bucket).
- `hld(g, limit=12)` — `flowchart LR`. Buckets files by package (or by filename when there are
  under 3 packages), counts `CALLS|INSTANTIATES` weights between buckets, takes the 22 heaviest
  edges, labels each node with `"<name><br/><small>N files</small>"`, and emits two `classDef`s
  (`hub` for the top 3 by weight, `mod` otherwise) so the canvas is styled without JS.
- `lld(g, limit=8)` — `classDiagram`. Ranks classes by `in_degree + out_degree`, lists up to 6
  non-underscore methods each, and draws `Base <|-- Derived` for in-corpus `INHERITS` edges.
- `flow(g, steps=9)` — `sequenceDiagram` with `autonumber`. Scores every candidate entry point by
  cross-package fan-out, then does a depth-first walk preferring same-owner calls, emitting
  `participant` lines on demand. Has a hardcoded 4-line fallback when the graph has no call edges.
- `handbook(g, name, description, invariants)` — the 7-chapter markdown: Executive Summary (file /
  class / function / edge counts), Package Purpose (file counts per bucket), Core Components (top
  classes by in-degree with paths), Data & Execution Lifecycle (top 8 functions by fan-in),
  Scalability (strongly-connected-component count as a cycle count, plus the hottest symbol named
  as the thing to trace first), and Governance Report (✅/❌ per invariant).

### 5.6 `src/agentic/` — the assistant branch

**`_00_cpg_tools.py`** — three tools, zero LLM calls, each returning a self-labelling dict
(`"tool": "<name>"`): `trace_symbol_impact(symbol, g)`, `verify_architecture_rules(g)` (aggregates
`passed = all(...)`), `get_symbol_ast(symbol, g)` (exact-name or `::`-suffix matches, plus up to
20 predecessors as `called_by`).

**`_01_challenge.py`** — the SWE-harness generator. `find_seams(g, limit=8)` collects `Function`
nodes with **zero `CALLS` predecessors**, computes each one's `CALLS` fan-out, and sorts descending —
so the highest-fan-out never-called function is the best onboarding target.
`_starter_for` mints a pytest stub whose name is the sanitized symbol, raising `NotImplementedError`.
`generate_challenge(g, index=0)` returns `{title, description, target_file, symbol, starter_code,
failing_test, hints[2]}`, wrapping around the seam list by index, or `None` when there are no
seams ("this codebase is well covered").

### 5.7 `src/security/` — the trust boundary

**`_00_guardrail.py`** — `GUARDRAIL_MESSAGE` plus two regexes. `_OUT_OF_SCOPE` (essay, homework,
poem, recipe, horoscope, lottery, dating, politics, election, napoleon, shakespeare, "solve this",
"write me an essay", "who won", stock tips, medical, legal) always blocks. `_IN_SCOPE` (architect,
diagram, mermaid, dependency, import, call graph, function, class, module, refactor, dead code,
blast, impact, invariant, layer, coupling, cohesion, flow, trace, symbol, repo, codebase, test,
coverage, challenge, "explain this/the code/function/class/file") always passes. The gap is
decided by length: **≤ 6 words is treated as chit-chat and blocked; longer unknown questions are
passed to the model with repo context.** Fail-closed on the short side, fail-open on the long side.

**`_01_scrubber.py`** — brand protection. `_FINGERPRINTS` matches `gemini*`, `google-genai`,
`generativelanguage`, `text-embedding-N`, `gpt-*`, `claude*`, `llama*`; `_BACKEND_TAG` matches
`Backend: X`. `scrub` rewrites `Backend: …` → `Engine: ArchiMind Neural Graph Core` and then
replaces every remaining fingerprint with the same label. `engine_label()` returns
`ENGINE_LABEL` for API responses and the UI pill. The effect is that no provider name can reach
the browser, which is exactly what `test_no_model_names_leak_in_chat` and
`test_scrubber_masks_fingerprints` enforce.

### 5.8 `src/storage/` — persistence branch

**`_00_sqlite_cache.py`** — a 40-line `CacheStore` around a single-file SQLite table
`cache(k TEXT PRIMARY KEY, v TEXT, ts INTEGER)`, with `put` (`INSERT OR REPLACE`), `get`
(JSON-decodes, returns `None` on anything malformed), and `keys`. Creates its parent directory.
Tested, but no production call site currently uses it.

**`_01_golden_repos.py`** — the demo loader. `FIXTURE_DIR` points at `src/storage/golden_fixtures`.
`golden_key(id)` → `golden:<id>`. `load_golden(id)` is `@lru_cache(maxsize=8)` and **rejects any id
that is not `str.isidentifier()`**, which is what blocks `../etc`. `public_view(doc)` strips
`cpg_artifact` (it is the largest key and the browser does not need raw node ids).
`list_golden(_store=None)` returns light cards `{id, title, subtitle, repo_url, cached, stats}` —
the unused `_store` parameter is a leftover from a removed `CacheStore` integration.

**`golden_fixtures/pytorch.json`** — 1224 nodes / 2469 edges, 50 files, 234 classes, 928 functions.
Scope `torch/nn/modules`, `torch/optim`. Keys: `chat_response` (the handbook), `chat_summary`,
`cpg_artifact`, `engine`, `flow_mermaid`, `hld_mermaid`, `id`, `invariants`, `lld_mermaid`, `name`,
`repair_log`, `repo_url`, `scope`, `stats`, `subtitle`, `title`.
**`golden_fixtures/openclaw.json`** — 325 / 543, 60 files, 8 classes, 256 functions. Scope
`src/agents/harness`, `src/agents`.
**`golden_fixtures/requests.json`** — 333 / 680, 19 files, 52 classes, 240 functions. Scope
`src/requests`.
All three are committed JSON, so the demo is compute-free and network-free on any deploy.

### 5.9 `src/variations/`
Present on disk, **empty**, and not in git. A reserved experiment slot.

---

## 6. `static/` — Frontend

### `static/css/` — the design system
- **`00_variables.css`** (42) — the token layer: dark palette, radii, spacing, type scale. Loaded by
  every page through the base template.
- **`01_landing.css`** (60) — the hero, the search row, the demo card grid, skeletons.
- **`02_studio.css`** (140) — topbar, tab strip, five tabpages, handbook reader + TOC, invariant
  cards, assistant aside, composer, FAB, responsive collapse.
- **`03_canvas.css`** (34) — the pan/zoom viewport, the stage, the mermaid host, the canvas
  toolbar, the HLD/LLD/Flow sub-tabs.

### `static/js/`
- **`01_pan_zoom.js`** (117) — an `IIFE` exposing `PanZoom(viewport, stage)`: pointer-driven pan,
  wheel/pinch zoom, fit-to-screen, fullscreen, and SVG export. The `up(e)` handler finalises a
  gesture. Loaded before the studio script because the studio instantiates it.
- **`02_studio_tabs.js`** (47) — tab switching (`data-stab` ↔ `data-page`) plus two off-canvas
  drawers (`chat-open`, `toc-open`) with a shared backdrop, Escape-to-close, and a
  `matchMedia("(min-width: 1024px)")` listener that auto-closes when the layout goes wide. It
  dispatches a `studio:tab` CustomEvent so `00_studio.js` can react without coupling.
- **`03_challenge_ui.js`** (44) — `ChallengeUI.load(query)`: fetches `/api/challenge`, renders title /
  description / target / starter code in a `<pre>`, a "Copy failing test" button (clipboard, with
  `"Copied ✓"` feedback), and a "Next challenge" button that bumps a random `&n=`. It escapes all
  interpolated text.
- **`00_studio.js`** (302) — the controller, and the only file that knows the API. `api(url, opts)`
  unwraps `{ok, j}`; `md(text)` is a small markdown renderer; `codeFor(kind)` picks
  `hld_mermaid`/`lld_mermaid`/`flow_mermaid` (golden) or `*_graph.mermaid_code` (live);
  `render()` calls `mermaid.render` into `#mermaidHost` and hands the SVG to `paint()`;
  `fillHandbook()`, `fillGovern()` (invariants + blast form), `fillResearch()` (stats + repair
  badges), `fillChips()` (suggested questions); `scopeQuery()` decides whether a workspace ref is a
  golden id or an analysis id; `trace(e)` posts the blast-radius query; `bubble` appends a chat
  message; `ask(e)` posts `/api/chat`; `progress(s)` renders a stage; `poll()` loops
  `/api/status`; `boot()` reads `data-ref` and dispatches to the golden or live path. Loaded last,
  `defer`, after its dependencies.

### `static/doc.css` (569) and `static/doc.js` (328) — the legacy results page
`doc.css` is a full standalone dark theme (its own `:root` tokens, not shared with the studio).
`doc.js` reads `window.__ARCHIMIND_DATA__`, uses `window.marked` + `window.DOMPurify` when present,
renders the handbook, builds a chapter TOC from `h2`s with an `IntersectionObserver` highlight
spy, appends chat messages, offers `buildDownload` (blob export), and calls `renderGraph(name,
canvasId)` for the three diagrams. This is the older single-page results view; the studio
supersedes it, and `/doc` still serves it.

---

## 7. `templates/` — Server-Rendered Shells

- **`00_base.html`** (17) — the only layout: doctype, viewport, `{% block title %}`,
  `{% block head %}`, preconnect + Inter from Google Fonts, `00_variables.css`, `{% block body %}`.
- **`01_landing.html`** (65) — the hero (logo, headline, sub), a `#landingForm` with `#landingUrl`
  and an Analyze button, a `#landingNotice` status card, and a `#demoCards` showcase. All logic is
  inline vanilla JS: submit → `POST /api/analyze` → redirect to `/workspace/<analysis_id>`; then
  `GET /api/golden` → build `<a class="card">` elements pointing at
  `/workspace/golden:<id>`. Auth state toggles Sign In vs Logout.
- **`02_studio.html`** (122) — the five-tab studio. Loads `02_studio.css` + `03_canvas.css` and
  mermaid 11 from jsdelivr, then the four JS modules in dependency order. The topbar carries the
  fixed `Engine: ArchiMind Neural Graph Core` pill. Tabs are `canvas` / `handbook` / `govern` /
  `agent` / `telemetry`; the canvas holds the mermaid host, a 5-button toolbar
  (`zin, zout, fit, full, svg`) and the HLD/LLD/Flow sub-tabs; handbook is a TOC + scroll reader;
  govern holds the `#blastSymbol`/`#blastBtn` tracer and `#invariantCards`; agent holds
  `#challengeBtn`/`#challengeOut` plus three cards documenting the CPG tools; telemetry holds
  `#telemetryStats`, `#repairBadges`, `#workspaceStats`. The right rail is the assistant
  (`#chatLog`, `#chips`, `#chatForm`, `#chatQ` with `maxlength=250`), plus a mobile `#chatFab` and
  `#backdrop`.
- **`doc.html`** (900) — the legacy results page, self-contained: a large inline `<style>` block
  defining its own dark palette, then meta, chapter nav, markdown body, three diagram canvases,
  the chat stream, and CDN `marked`/`DOMPurify`/mermaid. Data arrives as
  `window.__ARCHIMIND_DATA__`.
- **`login.html`** (103) and **`sign_up.html`** (123) — the classic forms. They post to
  `app.py`'s handlers and render `flash()` categories.

---

## 8. `scripts/` — Operations

Numbered prefixes encode execution order; unnumbered names are topic scripts.

| Script | What it does |
|---|---|
| `00_build_and_push_image.sh` | Sources the preflight, creates/uses a named buildx builder, bootstraps it, force-removes old local images for the repo, then `buildx build --pull --platform linux/amd64,linux/arm64` with two tags (`latest` + timestamp) and `--push` (or `--load` for single-platform). Refuses multi-platform without `PUSH_IMAGE=1`. |
| `01_smoke_test_container.sh` | Requires `.env`, builds `archimind:smoke`, runs it detached on port 5050 with `--env-file`, polls `/api/status` 20× every 3 s, prints the payload on success, dumps `docker logs` on failure, and always cleans up via an `EXIT` trap. |
| `02_convert_dot_to_drawio.py` | A hand-written DOT parser: `parse_attrs`, `parse_dot` (title, `rankdir`, `graph/node/edge` defaults, nodes, edges), `compute_positions` (BFS longest-path layering into layers, then a simple grid — TB vs LR), `node_dimensions`, `html_label`, `node_style` (maps box/ellipse/cylinder/note/component/circle/doublecircle + dashed), `edge_style` (orthogonal), and `build_drawio` emitting draw.io `mxfile`/`mxGraphModel` XML via `ElementTree`. Converts every `*.dot` in `--input-dir` (default `docs/diagrams`). |
| `build_golden_cache.py` | The fixture generator: `fetch_subtree` → `build_graph` → `check_invariants` → `hld/lld/flow` → **raises if any diagram fails `validate_mermaid`** → assembles `stats`, a `chat_summary`, the `handbook` as `chat_response`, `repair_log {hld:1,lld:1,flow:1}`, and `to_compact(g)` as `cpg_artifact` → writes minified JSON to `FIXTURE_DIR`. Accepts ids as argv to rebuild selectively. |
| `deploy_pi.sh` | Sources `.env`, `ssh mkdir`, `scp` the compose file (as `docker-compose.yml`) and `.env`, installs Docker + the compose plugin on the Pi if missing, `docker compose pull && up -d`, then prints `ps`, `logs --tail=50`, and a health curl. |
| `deploy_pi_build.sh` | The *other* deployment shape: tars the whole project (excluding `.git`, `venv`, `__pycache__`, `data/chroma_db`, `data/temp_repo`), scps it, installs Docker + `build-essential` remotely, extracts, `compose down`, `build --no-cache`, `up -d`, then health-checks. Use this when you must build on the Pi rather than pull a prebuilt multi-arch image. |
| `docker_preflight.sh` | Three sourced helpers: `require_docker_cli`, `require_docker_daemon` (checks `docker info`, then `/var/run/docker.sock` existence, then `systemctl is-active docker`, and emits targeted fixes including a rootless-Docker hint), `require_docker_buildx`. This is why the other scripts fail fast with an actionable message instead of a confusing build error. |
| `install_pi_autostart_cron.sh` | Remote heredoc: `systemctl enable docker`, `mkdir -p`, then idempotently installs `@reboot cd $PI_DIR && docker compose up -d >> cron-start.log` into the Pi's crontab (greps the old line out first). |
| `probe_diagrams.py` | A **real** Mermaid v11 conformance probe: launches chromium via Playwright, loads mermaid 11 from jsdelivr, `mermaid.render`s each golden diagram, prints `OK` / `FAIL: <message>`, and screenshots successes to `/tmp/g_<id>_<kind>.png`. This is how the "valid-by-construction" claim is actually verified against the browser, complementing the regex validator. |
| `run_local.sh` | `mkdir -p data data/chroma_db data/temp_repo`, require `.env`, `python3 app.py`. |
| `run_worker.sh` | Usage-checked; `mkdir -p` the data dirs; `python3 worker.py <url> [id]`. |
| `setup_local.sh` | Checks `python3` and `pip`, creates the data dirs, copies `.env.example` → `.env` if absent, `pip install -r requirements-dev.txt`, prints the next step. |
| `soak_test.py` | The load rig. A fixed rotating endpoint plan of read-only paths (`/`, `/api/golden`, `/api/status`, an intentional-400 `/api/analyze`, three `/api/blast-radius` calls, one unknown-symbol blast) — write paths are excluded by design. Paces submissions with a deadline loop, caps inflight at 200 (a backpressure bound, not a result buffer), records every latency into a lock-guarded list, and runs a daemon thread that samples server RSS from `ps` every minute. Emits p50/p95/p99/max/mean, error rate, status histogram, peak RSS, and a `PASS` verdict at < 1 % errors, appending one JSON line to `--out`. |
| `test_all.sh` | The full gate in order: `tests/unit`, `tests/integration`, the legacy root suite, `tests/e2e` (tolerated to fail — no browser in CI), then `ruff check` over `src/`, `build_golden_cache.py`, `00_main.py`, `app.py`, `worker.py`. |
| `test_local.sh` | `DATABASE_URL=sqlite:///:memory:` + a fixed `SECRET_KEY`, then `pytest tests/ -v --cov=.`. |

---

## 9. `tests/` — The Safety Net

### `tests/conftest.py`
Sets the environment **before any app import**: a temp-file SQLite URL,
`SECRET_KEY=test-secret-key`, `VECTOR_BACKEND=local`, and blanked `GEMINI_API_KEY` /
`PINECONE_API_KEY`. This single file is why the suite is hermetic.

### `tests/test_config.py` (26)
Two cases that pin the `DATABASE_URL` normaliser: a schemeless token falls back to
`SQLITE_URL`; `postgresql://` is rewritten to `postgresql+psycopg://`.

### `tests/test_app.py` (124)
Route-level: `/` returns 200; `POST /api/analyze` with no URL is 400; `/api/preview` is mocked at
`RepositoryService.get_repository_preview` and must return `full_name`; `/api/chat` is double-mocked
(`VectorStoreService`, `DocumentationService`) and asserts the answer passes through, the engine
label is the scrubbed one, **no `backend` key leaks**, and the collection name is `example__repo`;
`/api/analyze` success is 202 with `Popen` patched and one `AnalysisLog` row created;
`/api/check-limit` shape for anonymous; and `User.get_analysis_count()`.

### `tests/test_services.py` (259) — the biggest test file
`_SimpleCollection` add/query; `query_similar_documents` producing `File:` + `github_url=` headers;
**a staleness test** that writes an index, clears it out-of-band, rewrites one record, and asserts
a freshly constructed service sees only the new data (i.e. no in-process caching bug);
`generate_all_documentation` returning exactly the five keys; a grounded-fallback test using a
fake RNAtoDNA context that asserts `LangGraph` never appears and `Flask` does; two Gemini tests
that patch `services.genai`/`genai_types` and assert the exact `ThinkingConfig`,
`GenerateContentConfig` kwargs, call counts (5 for `generate_all`, 1 for chat), and prompt
contents; a local chat-answer test asserting `"Direct answer:"`, `main.py`, and `Flask`; URL
parsing for both https and SSH forms; and `_select_remote_paths` keeping README/docs/service
while dropping `assets/image.png`.

### `tests/test_worker.py` (119)
Fence stripping; invalid JSON → error status; a fully-mocked happy-path `run_analysis` that
patches `config.STATUS_FILE_PATH`/`LOCAL_CLONE_PATH`/`CHROMA_DB_PATH`/`EMBEDDING_MODEL`/extensions
plus `_update_database_log` and `_save_to_history`, then asserts `completed`, `progress == 100`,
`hld_graph.status == "ok"`, and `vector_service.reset()` called once; and a refresh test asserting
`generate_embeddings` is called with the fresh file map.

### `tests/test_repository_service.py` (94)
Clone short-circuits on an existing path; `clone_from` is called; the extension/ignored-dir filter;
a custom `_PartialReadResponse` that raises `IncompleteRead` to prove partial payloads are used; a
two-response `side_effect` list proving `_http_get_json` retries after a truncated partial; and
`build_collection_name` lowercasing.

### `tests/test_integration.py` (26)
One case: `/api/analyze` returns 202 and calls `Popen`.

### `tests/unit/test_cpg_engine.py` (134) — the precision suite
The most valuable tests in the repo, each with a rationale in its docstring:
`extract_module` finds classes/methods/calls; a broken file yields `parse_ok is False` instead of
raising; **every `CALLS` edge targets a real declared symbol** (the precision-1.0 claim);
`blast_radius` is reverse reachability (a dead method impacts nothing); `self.helper()` binds to
the owning class only (`B.helper` in another file is unaffected); TypeScript extraction asserts
`classes == {"Runner": ["Base"]}` and `imports["Base"] == "./base.js"`; the closure gate withholds
`RichHandler.emit` because `Handler` is out-of-corpus while certifying
`UserRepo.dead_method`; `to_compact`/`from_compact` round-trips nodes, edges, and blast results;
all three invariant ids are present; a hand-built presentation→data `IMPORTS` edge fails
isolation; the optimizer heals a bad first draft in exactly 2 attempts and stops at the cap; the
tarball URL builder rejects non-GitHub before any network call; and `impact()` returns names,
count, and sub-second timing.

### `tests/unit/test_mermaid_conformance.py` (46) — the regression
The docstring records the origin: analyzing `LeevAI-Devs/webpage` produced `Init[init()]`, which
Mermaid v11 rejects, and the old validator passed it — so the repair loop never fired and
`repair_log` read 1/1/1. Six tests: parens in a flowchart label are rejected; `normalize_mermaid`
entity-encodes them into something that validates; escaped-newline payloads are rejected with
*"needs unescaping, not reflection"*; normalizing unescapes them; unbalanced brackets are caught;
and numeric entities (`#40;`/`#41;`) are not flagged by the validator's own `#` rule.

### `tests/unit/test_ingestion_storage.py` (62)
`keep_member` accepts `pkg/mod.py` and rejects oversized, `tests/`, `.png`, and `.md`;
`decode_sources` caps and dedupes; `repo_tarball_url` raises `ValueError` for garbage and for
gitlab; `CacheStore` round-trips; and a golden-fixture test that asserts all three fixtures are
bundled, **every diagram in every fixture passes `validate_mermaid`**, the artifacts are non-empty,
the handbooks contain `## Executive Summary`, and `load_golden("../etc")` returns `None`.

### `tests/unit/test_agentic_security.py` (60)
Guardrail blocks essay/homework/hi/empty and passes blast-impact, invariant, and long architecture
questions; the scrubber kills every provider fingerprint; all three CPG tools resolve against a
2-file graph; the challenge carries all six required keys including a `pytest` reference; and a
fully-called graph yields no seams.

### `tests/integration/test_engine_resources.py` (71)
`tracemalloc` + `ru_maxrss` around a 31-file CPG build, asserting traced memory < 50 MB and RSS
growth < 150 MB (with a `ponytail:` note that `ru_maxrss` is process-wide so the *growth* is what
is asserted); the 429 concurrency guard; the golden list/detail shape including the 404; blast
radius 400 vs 404; and a real blast trace over the PyTorch fixture under 2000 ms.

### `tests/integration/test_studio_security.py` (73)
Landing contains `landingUrl`/`demoCards`/`Analyze`; the workspace serves all five
`data-stab` anchors; the essay prompt trips the guardrail **without touching the model**;
overlong questions are 400 and the 6th anonymous chat is 403/404; `/api/challenge` 404s without a
graph and serves PyTorch instantly; and a chat response contains neither `gemini` nor `Backend:`.

### `tests/e2e/test_studio_e2e.py` (115)
Playwright, `importorskip`'d so it vanishes when browsers are absent, with a module-scoped fixture
serving the app on `127.0.0.1:5125` via `werkzeug.make_server` in a daemon thread. Parametrised
over 4 viewports (390/768/1440/2560): the landing renders cards with
`scrollWidth <= innerWidth + 1` (no horizontal scroll), and PyTorch + OpenClaw render all three
diagrams with `#mermaidHost svg` present and no `Syntax error` text. Plus two desktop tests: all
five tabs switch (asserting the `active` class on the right `tabpage`) and the blast tracer
returns output; and the challenge renders while the essay prompt shows `Guardrail Triggered`.

### `tests/benchmarks/`
Empty on disk, not in git. Reserved.

---

## 10. `docs/` and `.github/`

- **`docs/README.md`** (137) — the operational reference. Explains why the root README is short,
  restates the runtime flow, tabulates required and optional env vars, walks local development,
  documents the Docker build/push and smoke-test commands (including the "your Docker daemon must
  be reachable" precondition), the Pi sequence, the diagram inventory, a validation checklist, and
  a "Current Constraints" section that admits the numbered-file rename was deliberately *not* done
  for `src/`'s siblings and that retrieval is still local-first.
- **`docs/RASPBERRY_PI_DEPLOYMENT.md`** (171) — the full Pi runbook: prerequisites, buildx
  multi-arch build, `.env` preparation, `deploy_pi.sh` usage, compose inspection, log reading,
  autostart, and troubleshooting.
- **`docs/AGENTS.md`** (38) — an agent-facing quickstart with YAML frontmatter (`name`,
  `description`, `applyTo: ArchiMind/**`, explicit exclusions for `data/vector_store` and
  `data/chroma_db` so agents never load those dumps into context). Lists common tasks and packaging.
- **`docs/CONTRIBUTING.md`** (62) — contribution rules (no secrets, keep local dev on
  `VECTOR_BACKEND=chroma`, root-cause fixes, respect module boundaries, update docs), coding
  expectations, database/retrieval guidance (Supabase in prod, SQLite locally, Pinecone optional),
  and a 5-item PR checklist with a suggested summary/risk/validation format.
  *Note: it says to maintain diagrams as `.drawio` and **not** reintroduce `.dot` sources — but
  `.dot` sources and `02_convert_dot_to_drawio.py` both exist. The doc is stale here.*
- **`docs/profiling.md`** (25) — the measured budgets, and the most concrete file here. A recorded
  soak of 15,000 requests at 100 rpm × 150 min on gunicorn 1×4: **0 errors**, p50 9.9 ms,
  p95 27.9 ms, p99 37.5 ms, max 937.5 ms, RSS 12.7 MB idle → 23.6 MB peak against a 380 MB
  ceiling (16× headroom); a 600 rpm burst probe 600/600 clean. Then a budget table (CPG build
  memory, blast-radius < 2000 ms vs 0.5 ms measured, ≤ 250 files per golden corpus vs 24/20/40,
  tarball ≤ 60 MB / ≤ 400 files) and the `MAX_CONCURRENT_JOBS = 1` → 429 note.
- **`docs/diagrams/`** — five Graphviz sources and their generated draw.io twins:
  `hld.dot/.drawio` (digraph with `rankdir=LR`, node/edge defaults, rounded boxes, cylinder stores,
  a `note` for `status.json`, a `component` for the Gemini API), `lld.dot/.drawio`,
  `flow.dot/.drawio`, `uml.dot/.drawio`, `use_cases.dot/.drawio`. Plus
  `.$use_cases.drawio.bkp` — a draw.io editor lock/backup artefact that is accidentally tracked and
  should be deleted and gitignored.
- **`.github/workflows/test.yml`** — CI: on push to `main`/`develop` and PRs to `main`; Python 3.11
  with pip caching over both requirements files; install `requirements-dev.txt`; lint
  (`black --check`, `isort --check-only`, `flake8 --select=E9,F63,F7,F82`); test with a SQLite CI DB
  and a dummy `GEMINI_API_KEY`, `pytest -v --maxfail=1`.
- **`.github/README.md`** (40) — explains the CI pipeline and how to reproduce it locally.
- **`.github/FUNDING.yml`** — all funding platforms present but every value left as a
  placeholder comment.
- **`webcache/backoff/export.arxiv.org`** — a two-line file (`1790394169`, `1`) left over from an
  arXiv HTTP backoff cache. Not used by any code; safe to delete.

---

## 11. Data Flow Diagram: Who Calls Whom

```
app.py
 ├── imports config, models, oauth_utils, services
 ├── imports (lazily, per request):
 │    src/config/_00_settings.SETTINGS          → max_concurrent_jobs
 │    src/storage/_01_golden_repos              → load_golden / public_view / list_golden
 │    src/agentic/_01_challenge.generate_challenge
 │    src/agentic/_00_cpg_tools.{trace_symbol_impact, verify_architecture_rules, get_symbol_ast}
 │    src/cpg/_01_cpg_builder.from_compact
 │    src/security/_00_guardrail.check_scope
 │    src/security/_01_scrubber.{scrub, engine_label}
 │    src/governance/_00_blast_radius.impact
 │    src/orchestration/_02_doc_synthesizer.cpg_context_block
 └── spawns: worker.py

worker.py
 ├── services.{RepositoryService, VectorStoreService, DocumentationService}
 ├── src/ingestion/_00_tarball_client.stream_files
 ├── src/ingestion/_01_file_filter.decode_sources
 ├── src/cpg/_01_cpg_builder.{build_graph, to_compact}
 ├── src/governance/_01_invariants.check_invariants
 ├── src/orchestration/_02_doc_synthesizer.cpg_context_block
 ├── src/orchestration/_03_cpg_diagrams.{hld, lld, flow}
 ├── src/orchestration/_01_eval_optimizer.{run_eval_optimizer, normalize_mermaid, validate_mermaid}
 └── (via create_app) models.AnalysisLog, oauth_utils.save_repository_to_history

src/orchestration/_01_eval_optimizer ──> _00_agent_state.DiagramState
src/orchestration/_02_doc_synthesizer ──> src/cpg/_01_cpg_builder
src/orchestration/_03_cpg_diagrams  ──> src/cpg/_01_cpg_builder
src/cpg/_01_cpg_builder             ──> src/cpg/_00_ts_ast.extract_module
src/cpg/_02_closure_gate            ──> src/cpg/_01_cpg_builder
src/governance/_00_blast_radius     ──> src/cpg/_01_cpg_builder
src/governance/_01_invariants       ──> src/cpg/_01_cpg_builder, src/config/_01_constants
src/agentic/_00_cpg_tools           ──> src/cpg/_01_cpg_builder, src/governance/_01_invariants
src/agentic/_01_challenge           ──> src/cpg/_01_cpg_builder
src/ingestion/_00_tarball_client    ──> src/ingestion/_01_file_filter, src/config/_00_settings
src/ingestion/_02_subtree_client    ──> src/ingestion/_01_file_filter
src/storage/_01_golden_repos        ──> src/config/_01_constants
scripts/build_golden_cache.py       ──> ingestion/_02, cpg/_01, governance/_01,
                                       orchestration/_01, orchestration/_03, storage/_01
```

The dependency graph is a clean DAG: `config` → `ingestion`/`cpg` → `governance`/`orchestration`/
`agentic` → `app`/`worker`/`scripts`. Nothing under `src/` imports a root module; the root never
leaks into `src/`.

---

## 12. Configuration Surface

**Read by `config.py` (legacy path):** `DATABASE_URL`, `EMBEDDING_MODEL`, `VECTOR_BACKEND`,
`PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `PINECONE_NAMESPACE`, `PINECONE_CLOUD`,
`PINECONE_REGION`, `PINECONE_DIMENSION`, `SMALL_SUMMARY_MODEL`, `GEMINI_API_KEY`/`GOOGLE_API_KEY`,
`DOCUMENTATION_MODEL`, `CHAT_MODEL`, `GEMINI_THINKING_LEVEL`, `GEMINI_API_VERSION`,
`DOCUMENTATION_CONTEXT_CHAR_LIMIT`, `REMOTE_FETCH_MAX_FILES`, `REMOTE_FETCH_CONCURRENCY`,
`REMOTE_FILE_MAX_BYTES`, `REQUEST_TIMEOUT_SECONDS`, `ANONYMOUS_GENERATION_LIMIT`,
`ENABLE_PERFORMANCE_HINTS`.

**Read by `src/config/_00_settings.py` (engine path):** `GEMINI_API_KEY`, `DOCUMENTATION_MODEL`,
`CHAT_MODEL`, `EMBEDDING_MODEL`, `MAX_CONCURRENT_JOBS`, `DATA_PATH`, `GOLDEN_CACHE_PATH`,
`TARBALL_MAX_MB`, `TARBALL_MAX_FILES`, `TARBALL_TIMEOUT_S`, `MERMAID_MAX_RETRIES`.

**Read only by `app.py`:** `SECRET_KEY`, `FLASK_DEBUG`, `FLASK_HOST`, `FLASK_PORT`,
`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `PREFERRED_URL_SCHEME`, `SESSION_COOKIE_SECURE`,
`SESSION_COOKIE_SAMESITE`.

**Read elsewhere:** `GITHUB_TOKEN` (`_02_subtree_client`), `OAUTHLIB_INSECURE_TRANSPORT` (Authlib),
`ARCHIMIND_IMAGE`/`DOCKERHUB_REPO`/`DOCKER_IMAGE_TAG`/`PI_USER`/`PI_HOST`/`PI_DIR` (deploy scripts).

**Filesystem layout at runtime:**

```
data/
  status.json                 ← mirror of the latest status
  status_<analysis_id>.json   ← per-analysis status + full result
  archimind_dev.db            ← SQLite (users, analysis_logs, repository_history)
  vector_store/               ← _SimpleCollection JSON, or ChromaDB persistent dir
    <owner>__<repo>_summaries.json
    <owner>__<repo>_chunks.json
  temp_repo/<name>_<id>/      ← clone fallback only
```

---

## 13. Where the README Lies

The root `README.md` was written for the pre-CPG architecture and is now behind the code in five
specific ways. Worth knowing before you trust it:

1. **It describes the LangGraph two-step retrieval as the primary mechanism.** It never mentions
   the Code Property Graph, tree-sitter, `src/cpg/`, invariants, blast radius, the challenge
   harness, or the golden fixtures — which is now the *headline* feature set.
2. **The UI described is `doc.html` only.** The actual product surface is the five-tab studio
   (`/workspace`), reached from a landing page with instant demo cards. `/doc` is legacy.
3. **The project structure block omits `src/` entirely** and lists only 8 of the 15 scripts.
4. **`PINECONE_DIMENSION` is inconsistent**: `config.py` defaults to 768, `.env.example` says the
   live index is 1024. A deployment that relies on the default will produce dimension mismatches.
5. **It recommends `black`/`isort`/`flake8`/`bandit` as the lint gate**, while `pyproject.toml`
   configures ruff and `scripts/test_all.sh` actually runs ruff.

Two more divergences outside the README:
- `requirements.txt` omits `tree-sitter-typescript`, so the TS path silently degrades to the
  Python-only stdlib fallback on a clean install and `test_typescript_extraction` will fail.
- `docs/CONTRIBUTING.md` forbids `.dot` sources, but `docs/diagrams/*.dot` and the converter script
  are the current source of truth.
- `auth.py` is dead code referencing a non-existent `index` endpoint; `src/variations/` is an empty
  directory; `docs/diagrams/.$use_cases.drawio.bkp` and `webcache/` are stale artefacts.

---

## 14. Untracked and Empty Things

Present in the working tree, not in git, and not part of the project:

- `.mypy_cache/`, `.ruff_cache/`, `__pycache__/` dirs — tool caches, already gitignored.
- `src/variations/`, `tests/benchmarks/`, `papers/templates/` — empty reserved directories.

### Complete File Index (all 110 tracked files)

| # | Path | One-line role |
|---|---|---|
| 1 | `.autoresearch-stop` | empty marker telling the autoresearch loop to stop |
| 2 | `.coveragerc` | coverage source/omit/exclude configuration |
| 3 | `.dockerignore` | build-context exclusions (`.env`, `.git`, `/data/`) |
| 4 | `.env.example` | annotated 100-line env surface incl. AGENT INSTRUCTION header |
| 5 | `.gitignore` | secrets, Python, venv, IDE, `data/`, coverage, tool caches |
| 6 | `.github/FUNDING.yml` | funding platforms, all placeholdered |
| 7 | `.github/README.md` | explains the CI pipeline and local reproduction |
| 8 | `.github/workflows/test.yml` | CI: py3.11, black/isort/flake8, pytest with SQLite |
| 9 | `00_main.py` | production entrypoint; `app = create_app()` |
| 10 | `Dockerfile` | 2-stage build, non-root user, gunicorn CMD, HEALTHCHECK |
| 11 | `README.md` | landing-page documentation (partly stale, §13) |
| 12 | `app.py` | Flask app: 18 routes, auth, rate limits, CSP, worker spawn |
| 13 | `auth.py` | **dead** auth Blueprint; references a removed `index` endpoint |
| 14 | `config.py` | legacy env config + `DATABASE_URL` normaliser |
| 15 | `docker-compose.pi.yml` | pull-only compose for the Raspberry Pi |
| 16 | `docker-compose.yml` | local/Render compose with build + 2 gunicorn workers |
| 17 | `models.py` | `User`, `AnalysisLog`, `RepositoryHistory` (top-5 cap) |
| 18 | `oauth_utils.py` | Google OAuth blueprint + in-process history cache |
| 19 | `opencode.json` | disables the `composio` MCP server |
| 20 | `pyproject.toml` | ruff / black / mypy config |
| 21 | `requirements-dev.txt` | runtime reqs + pytest, coverage, lint, bandit |
| 22 | `requirements.txt` | runtime pins only (no `tree-sitter-typescript`) |
| 23 | `services.py` | `RepositoryService`, `VectorStoreService`, `DocumentationService` |
| 24 | `setup.sh` | root wrapper around `scripts/setup_local.sh` |
| 25 | `worker.py` | 8-stage background analysis pipeline + Mermaid sanitiser |
| 26 | `docs/AGENTS.md` | agent quickstart with `applyTo`/`exclude` frontmatter |
| 27 | `docs/CONTRIBUTING.md` | contribution rules + PR checklist (stale on `.dot`) |
| 28 | `docs/README.md` | operational reference: runtime, env, Docker, validation |
| 29 | `docs/RASPBERRY_PI_DEPLOYMENT.md` | full Pi runbook |
| 30 | `docs/profiling.md` | measured soak + engine budgets (0 errors, 23.6 MB peak) |
| 31 | `docs/diagrams/.$use_cases.drawio.bkp` | tracked draw.io lock/backup artefact — delete it |
| 32 | `docs/diagrams/flow.dot` | Graphviz source: end-to-end flow |
| 33 | `docs/diagrams/flow.drawio` | generated draw.io twin of `flow.dot` |
| 34 | `docs/diagrams/hld.dot` | Graphviz source: high-level design |
| 35 | `docs/diagrams/hld.drawio` | generated draw.io twin of `hld.dot` |
| 36 | `docs/diagrams/lld.dot` | Graphviz source: low-level design |
| 37 | `docs/diagrams/lld.drawio` | generated draw.io twin of `lld.dot` |
| 38 | `docs/diagrams/uml.dot` | Graphviz source: UML |
| 39 | `docs/diagrams/uml.drawio` | generated draw.io twin of `uml.dot` |
| 40 | `docs/diagrams/use_cases.dot` | Graphviz source: use cases |
| 41 | `docs/diagrams/use_cases.drawio` | generated draw.io twin of `use_cases.dot` |
| 42 | `scripts/00_build_and_push_image.sh` | buildx multi-arch build + push (amd64/arm64) |
| 43 | `scripts/01_smoke_test_container.sh` | build, run, poll `/api/status` until healthy |
| 44 | `scripts/02_convert_dot_to_drawio.py` | hand-written DOT → draw.io XML converter |
| 45 | `scripts/build_golden_cache.py` | subtree → CPG → validated diagrams → fixture JSON |
| 46 | `scripts/deploy_pi.sh` | scp compose + `.env` to the Pi, pull, up, health-check |
| 47 | `scripts/deploy_pi_build.sh` | tar + scp the whole project, build on the Pi |
| 48 | `scripts/docker_preflight.sh` | sourced daemon/CLI/buildx checks with targeted fixes |
| 49 | `scripts/install_pi_autostart_cron.sh` | installs an idempotent `@reboot` compose-up crontab |
| 50 | `scripts/probe_diagrams.py` | renders goldens in real Mermaid v11 via Playwright |
| 51 | `scripts/run_local.sh` | mkdir data dirs, require `.env`, `python3 app.py` |
| 52 | `scripts/run_worker.sh` | CLI wrapper: `worker.py <url> [id]` |
| 53 | `scripts/setup_local.sh` | check tools, create dirs, seed `.env`, install dev reqs |
| 54 | `scripts/soak_test.py` | paced load rig: percentiles, error rate, RSS sampling |
| 55 | `scripts/test_all.sh` | unit → integration → legacy → e2e → ruff gate |
| 56 | `scripts/test_local.sh` | in-memory SQLite + `pytest --cov=.` |
| 57 | `src/__init__.py` | engine package docstring |
| 58 | `src/agentic/__init__.py` | empty package marker |
| 59 | `src/agentic/_00_cpg_tools.py` | 3 deterministic tools: impact, rules, symbol AST |
| 60 | `src/agentic/_01_challenge.py` | untested-seam discovery + pytest challenge generator |
| 61 | `src/config/__init__.py` | empty package marker |
| 62 | `src/config/_00_settings.py` | Pydantic `Settings` + shared `SETTINGS` instance |
| 63 | `src/config/_01_constants.py` | extensions, ignored dirs, caps, invariant ids, `GOLDEN_REPOS` |
| 64 | `src/cpg/__init__.py` | empty package marker |
| 65 | `src/cpg/_00_ts_ast.py` | tree-sitter (+ `ast` fallback) symbol/call extraction |
| 66 | `src/cpg/_01_cpg_builder.py` | graph build, resolution ladder, blast radius, compact I/O |
| 67 | `src/cpg/_02_closure_gate.py` | out-of-corpus base witness; `certified_dead` |
| 68 | `src/governance/__init__.py` | empty package marker |
| 69 | `src/governance/_00_blast_radius.py` | `impact(symbol, artifact)` with timing |
| 70 | `src/governance/_01_invariants.py` | 3 structural Clean-Architecture rules |
| 71 | `src/ingestion/__init__.py` | empty package marker |
| 72 | `src/ingestion/_00_tarball_client.py` | chunked codeload tarball streaming with size cap |
| 73 | `src/ingestion/_01_file_filter.py` | `keep_member` gate + `decode_sources` |
| 74 | `src/ingestion/_02_subtree_client.py` | bounded contents-API subtree fetch for monorepos |
| 75 | `src/orchestration/__init__.py` | empty package marker |
| 76 | `src/orchestration/_00_agent_state.py` | `DiagramState` TypedDict for the repair loop |
| 77 | `src/orchestration/_01_eval_optimizer.py` | `normalize_mermaid` / `validate_mermaid` / LangGraph loop |
| 78 | `src/orchestration/_02_doc_synthesizer.py` | `cpg_context_block` grounding + `synthesize` |
| 79 | `src/orchestration/_03_cpg_diagrams.py` | valid-by-construction hld/lld/flow + `handbook` |
| 80 | `src/security/__init__.py` | empty package marker |
| 81 | `src/security/_00_guardrail.py` | scope regexes; ≤6-word unknown input is blocked |
| 82 | `src/security/_01_scrubber.py` | provider-fingerprint scrubber + engine label |
| 83 | `src/storage/__init__.py` | empty package marker |
| 84 | `src/storage/_00_sqlite_cache.py` | `CacheStore` key → JSON doc (+ timestamp) |
| 85 | `src/storage/_01_golden_repos.py` | fixture loader, `lru_cache`, `public_view`, `list_golden` |
| 86 | `src/storage/golden_fixtures/openclaw.json` | 325 nodes / 543 edges, 60 files |
| 87 | `src/storage/golden_fixtures/pytorch.json` | 1224 nodes / 2469 edges, 234 classes |
| 88 | `src/storage/golden_fixtures/requests.json` | 333 nodes / 680 edges, 52 classes |
| 89 | `static/css/00_variables.css` | design tokens (dark palette, radii, type) |
| 90 | `static/css/01_landing.css` | hero, search row, demo cards, skeletons |
| 91 | `static/css/02_studio.css` | topbar, tabs, readers, assistant, responsive |
| 92 | `static/css/03_canvas.css` | pan/zoom viewport, mermaid host, toolbar, sub-tabs |
| 93 | `static/doc.css` | standalone dark theme for the legacy `/doc` page |
| 94 | `static/doc.js` | legacy results page: markdown, TOC spy, diagrams, chat |
| 95 | `static/js/00_studio.js` | studio controller: API, mermaid, tabs content, chat, poll |
| 96 | `static/js/01_pan_zoom.js` | `PanZoom` constructor: pan, zoom, fit, fullscreen, export |
| 97 | `static/js/02_studio_tabs.js` | tab switching + off-canvas drawers, `studio:tab` event |
| 98 | `static/js/03_challenge_ui.js` | fetch/render/copy/next for the challenge card |
| 99 | `templates/00_base.html` | the only layout: `title`/`head`/`body` blocks |
| 100 | `templates/01_landing.html` | hero + analyze form + golden demo cards |
| 101 | `templates/02_studio.html` | five-tab studio: canvas/handbook/govern/agent/telemetry |
| 102 | `templates/doc.html` | legacy results page, self-contained inline CSS |
| 103 | `templates/login.html` | classic login form + flash messages |
| 104 | `templates/sign_up.html` | registration form with client-side field hints |
| 105 | `tests/__init__.py` | test package marker |
| 106 | `tests/conftest.py` | sets env before any import: temp SQLite, blank keys |
| 107 | `tests/e2e/__init__.py` | e2e package marker |
| 108 | `tests/e2e/test_studio_e2e.py` | Playwright, 4 viewports, mermaid renders, guardrail |
| 109 | `tests/integration/__init__.py` | integration package marker |
| 110 | `tests/integration/test_engine_resources.py` | memory ceiling, 429 guard, golden/blast endpoints |
| 111 | `tests/integration/test_studio_security.py` | routes, guardrail, quota, challenge, no model leakage |
| 112 | `tests/test_app.py` | Flask route tests with mocked services |
| 113 | `tests/test_config.py` | `DATABASE_URL` normalisation |
| 114 | `tests/test_integration.py` | analyze endpoint spawns the worker |
| 115 | `tests/test_repository_service.py` | clone, filters, partial-read recovery, collection naming |
| 116 | `tests/test_services.py` | collections, index staleness, Gemini mocks, grounded fallback |
| 117 | `tests/test_worker.py` | fence stripping, parse errors, full happy path, index refresh |
| 118 | `tests/unit/__init__.py` | unit package marker |
| 119 | `tests/unit/test_agentic_security.py` | guardrail, scrubber, CPG tools, challenge schema |
| 120 | `tests/unit/test_cpg_engine.py` | precision, self-call binding, closure gate, optimizer healing |
| 121 | `tests/unit/test_ingestion_storage.py` | member filter, tarball guards, cache, golden validity |
| 122 | `tests/unit/test_mermaid_conformance.py` | Mermaid v11 regression: `init()` labels, escaped newlines |
| 123 | `webcache/backoff/export.arxiv.org` | stale two-line arXiv backoff cache — delete it |

---

## Execution Walkthrough

The shortest complete path through the system, in order:

```bash
cp .env.example .env          # set SECRET_KEY; GEMINI_API_KEY optional
bash scripts/setup_local.sh   # venv-free install of requirements-dev.txt
bash scripts/run_local.sh     # Flask on 127.0.0.1:5000

# instantly, with no analysis: open / and click a demo card
#   -> /workspace/golden:pytorch
#   -> 00_studio.js sees the golden: prefix -> GET /api/golden/pytorch
#   -> mermaid.render into #mermaidHost, HLD/LLD/Flow sub-tabs
#   -> Impact tab: GET /api/blast-radius?symbol=Module&golden=pytorch
#   -> Challenge tab: GET /api/challenge?golden=pytorch

# for a real repository:
curl -XPOST localhost:5000/api/analyze -H 'Content-Type: application/json' \
     -d '{"repo_url":"https://github.com/psf/requests"}'
curl "localhost:5000/api/status?analysis_id=1"    # poll stage/progress
open http://127.0.0.1:5000/workspace/1

bash scripts/test_all.sh      # unit + integration + legacy + e2e + ruff
python3 scripts/soak_test.py --rpm 100 --duration-min 150 --server-pid <pid>
```

Rebuild the demos after a CPG change:

```bash
python3 scripts/build_golden_cache.py            # all three
python3 scripts/build_golden_cache.py pytorch    # just one
python3 scripts/probe_diagrams.py pytorch        # render in real mermaid v11 + screenshot
```
