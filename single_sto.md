# STO — Single Takeaway Overview: everything changed in ArchiMind

Two branches, all pushed to `github.com/krishnakumarbhat/ArchiMind`:
- `research/archimind-cpg-harness-20260925` — autonomous research loop (runs 1–14)
- `build/production-reengineering` — production rebuild (this doc's main subject)

---

## Phase 0 — Diagnosis (before any code)

Verified from source that ArchiMind was a linear RAG pipeline, not an agent:
`worker.py:252 run_analysis` hardcodes ingest→index→retrieve→generate→parse;
the only LangGraph graph (`services.py:1147-1156`) is 3 straight edges
(`select_files → collect_chunks → render_context → END`), zero `add_conditional_edges`,
zero `bind_tools`/`ToolNode`, single-shot `generate_content` (`services.py:1262`),
JSON failure swallowed as `{"status":"error"}` (`worker.py:188-211`), Mermaid "repair"
was regex only. This grounded the whole programme: add tool-calling + cycles +
deterministic validation instead of rebuilding a Claude Code clone.

## Phase 1 — Autonomous research loop (14 runs, ~18h, research branch)

- Setup: branch, `autoresearch_research.md/jsonl`, `experiments/worklog.md`,
  `equations.md` (42 rows), `strategies.md`, strategy-graph JSONL, `papers/notes/`,
  `scripts/run_auto_research.py` benchmark runner, 5 synthetic fixtures.
- Model probe: key valid (50 models); `gemini-3.8-flash`=503 (not provisioned),
  `gemini-2.5-flash`=404 (retired), `text-embedding-004`=404 → adopted
  `gemini-3.1-flash-lite-preview` + `gemini-embedding-001`, wired via gitignored `.env` only.
- Results: v0 regex precision **0.2143 → CPG 1.0** (same fixture/oracle);
  recall stuck at 0.5 (attribute-on-instance); N10 protocol manifest killed on prior
  art (Vulture whitelist + `vulture#430`); N11 impossibility result (in-corpus-only
  gate ≤ 1/2 on the discriminating pair); N14 headroom law (`|D∩T|−|D∩O| < 0`
  reverses L1); 4 metric-definition changes, all tagged, parity re-runs each time.
- Driver died 4× on watchdog stalls; recovered each time; closed out with
  `docs/leaderboard.md`, `docs/architecture.md`, `docs/profiling.md`,
  `docs/hld.drawio`, `docs/lld.drawio`, dashboard. Novelty peaked 46/100 → engineering track, no paper.

## Phase 2 — Backend engine `src/` (build branch, commits `fbf83cc`, `a1140aa`)

New packages (absolute imports, `_NN_` prefixes — `_00_` because Python identifiers
cannot start with digits — SRP one-concept-per-file, mypy-strict/ruff/black clean):
- `src/config/_00_settings.py` — Pydantic v2 Settings (env-driven, no secrets);
  `_01_constants.py` — extensions (`.py/.ts/.tsx/.js/.jsx/.mjs`), ignore dirs, 60MB/400-file
  caps, invariant ids, golden repo specs.
- `src/ingestion/_00_tarball_client.py` — zero-clone GitHub tarball streaming (64KB chunks);
  `_01_file_filter.py` — sanitizer/matcher/decoder; `_02_subtree_client.py` — bounded
  contents-API subtree fetch for GB-scale monorepos (per-dir + total caps).
- `src/cpg/_00_ts_ast.py` — tree-sitter Python **and** TypeScript/JavaScript extraction
  (classes, bases, methods, functions, imports, **scoped** calls with receivers),
  stdlib-ast fallback, error-tolerant (`parse_ok` flag).
- `src/cpg/_01_cpg_builder.py` — NetworkX DiGraph, CALLS resolved per-scope
  (self/this→owner class, same-file wins, import narrowing, ambiguous >3 refused),
  INSTANTIATES/INHERITS/IMPORTS/DEFINES edges, Tarjan SCC, BFS blast radius
  (**reverse** reachability: callers/instantiators/subclasses), compact JSON artifact.
- `src/cpg/_02_closure_gate.py` — out-of-corpus base witness; withholds protocol methods,
  one-directional (never creates false positives).
- `src/orchestration/_00_agent_state.py` — LangGraph DiagramState;
  `_01_eval_optimizer.py` — generate→validate→reflect cycle (cap 3), deterministic
  `validate_mermaid` (headers, bracket/paren balance, parens-in-`[]` labels,
  escaped-newline payloads, numeric-entity-aware `#` rule) + `normalize_mermaid`
  (unescape, subgraph quoting, paren→`#40;#41;` entities);
  `_02_doc_synthesizer.py` — CPG context grounding;
  `_03_cpg_diagrams.py` — valid-by-construction HLD (package map), LLD (class diagram),
  flow (hottest call chain), deterministic handbook.
- `src/governance/_00_blast_radius.py` — impact API helper;
  `_01_invariants.py` — presentation-isolation, acyclicity, domain-purity.
- `src/agentic/_00_cpg_tools.py` — `trace_symbol_impact`, `verify_architecture_rules`,
  `get_symbol_ast` (deterministic, zero LLM); `_01_challenge.py` — Challenge-Me task
  synthesis from zero-caller seams (title/description/target/starter/failing test/hints).
- `src/security/_00_guardrail.py` — repo-scope prompt filter (exact trigger message);
  `_01_scrubber.py` — provider/model masking → "ArchiMind Neural Graph Core".
- `src/storage/_00_sqlite_cache.py` — SQLite JSON store; `_01_golden_repos.py` —
  bundled fixture loader (`lru_cache`, path-traversal guard, light list view).
- `00_main.py` (deploy-compatible entry), `pyproject.toml` (ruff/black/mypy-strict),
  `requirements.txt` (+= networkx, pydantic(+settings), tree-sitter≥0.25, tree-sitter-python;
  tree-sitter unpinned from dead 0.21.3).
- Deviation from the brief, documented: PyTorch/Linux **full** repos infeasible
  (1.6GB/6.6GB tarballs vs 60MB cap; Linux is C, CPG reads Python/TS) → subsystem
  slices instead.

## Phase 3 — Pipeline wiring (`worker.py`, `app.py`)

- `worker.py`: tarball-first ingestion (legacy remote/clone fallback);
  CPG graph stage (≤300 files, 5000-node status cap); CPG context prepended to prompts;
  per-diagram evaluator-optimizer repair (`_generate_with_repair`, error feedback);
  `repair_log` attempts per diagram; deterministic `cpg_diagrams` fallback when LLM
  output fails validation (badge: "rebuilt from code graph"); result carries
  `cpg_artifact`, `invariants`, engine label; `generation_backend` masked.
- `app.py`: `MAX_CONCURRENT_JOBS=1` guard (HTTP 429 + retry flag);
  `/api/golden` (light list) + `/api/golden/<id>` (full workspace, no raw CPG);
  `/api/blast-radius` (golden or analysis artifact, <5ms); `/api/challenge`;
  `/` → landing, `/workspace`, `/workspace/<ref>` → studio (old workbench removed,
  see Phase 5); `_api_status` serves **completed** analyses cross-session
  (in-flight stays session-scoped); `_api_chat` upgraded — 250-char cap, guardrail,
  5-question anon quota, deterministic tool routing (impact/rules/signature intents,
  `tools_used` badges), golden-context fallback when no vector index, scrubbed answers,
  `engine` label (raw `backend` field removed).
- `config.py`: schemeless `DATABASE_URL` falls back to SQLite (fixed failing legacy test).
- Auth templates: removed personal UPI/phone donate links (privacy audit; no keys/tokens
  found anywhere in history or tree).

## Phase 4 — Golden demos (`scripts/build_golden_cache.py` → `src/storage/golden_fixtures/`)

Committed fixtures (work on any deploy, no DB needed):
- **PyTorch Core** — `torch/nn/modules` + `torch/optim` (50 files, 234 classes, 928 funcs, 503KB)
- **OpenClaw** — `src/agents` + `harness` (60 files, 256 funcs, 156KB; TS support added for this)
- **Requests HTTP** — `src/requests` (19 files, 52 classes, 133KB)
Each: stats, summary, deterministic handbook, 3 diagrams (validator-clean),
invariants, repair_log, full CPG artifact. Display titles, not raw handles.

## Phase 5 — Frontend rewrite (replaces 548-line workbench)

- **Landing** `01_landing.html` + `01_landing.css`: centered hero, example-prefilled
  search, 3 demo cards with live file/class counts; shared `00_base.html`.
- **Studio** `02_studio.html` + `02_studio.css`: topbar (brand, crumb, engine pill, auth),
  5 tabs (Canvas / Handbook / Impact / Challenge / Research), docked Copilot-style
  assistant (bubbles, typing dots, markdown answers, `tools_used` badges, suggestion chips)
  → slide-in drawer + 💬 FAB on mobile; TOC drawer; transform/opacity-only motion.
- **Canvas** `03_canvas.css` + `01_pan_zoom.js` (fit clamped ≥0.55 for legibility,
  pinch/wheel/drag/dblclick, fullscreen, SVG export): mermaid dark theme, 16px type,
  `useMaxWidth:false`, client-side LLM→code-graph fallback, impacted-node highlighting.
- **JS**: `00_studio.js` (boot, polling with pipeline progress, markdown reader, chat,
  blast, telemetry), `02_studio_tabs.js`, `03_challenge_ui.js` (copy/next-challenge).
  All `node --check` clean. Deleted: old `index.html`, `00_app.js`, `01_layout.css`,
  `02_ui_drawer.js`, `home.css`, `script.js`, legacy responsive e2e (superseded).

## Phase 6 — Mermaid v11 incident (commit `c1572a0`)

Real repo (`LeevAI-Devs/webpage`) produced `Init[init()]` → v11 flowchart parse error
while the old validator passed it (repair loop never fired). Bisected
statement-by-statement in headless Chromium; fixed via normalizer + strict validator
+ fallback (above); repaired `data/status_3.json` in place; verified all 3 diagrams
`RENDER_OK` in real mermaid 11.17.2; 6 conformance tests lock the exact samples.

## Phase 7 — Verification (all green, all committed)

- `bash scripts/test_all.sh`: **23 unit + 11 integration + 30 legacy + 18 Playwright e2e
  = 82 passed**, incl. landing→golden→workspace flows on 390/768/1440/2560px,
  challenge + guardrail-chat flows, zero-hscroll asserts, mermaid conformance suite.
- Gates: mypy-strict (29 files), ruff, black, `node --check` all clean.
- Soak: **100 req/min × 150 min = 15,000 reqs, 0 errors**, p50 9.9ms / p95 27.9ms,
  server RSS 12.7MB idle → 23.6MB peak (16× under ceiling). Rig: `scripts/soak_test.py`.
- Screenshots at desktop + mobile reviewed by eye (canvas, flow, handbook, impact,
  challenge, chat, landing): no overflow, no console errors.
- Pushed: `build/production-reengineering` (9 commits) + research branch; pre-push
  secret/PII scans clean; `main` untouched.

## Known limits (honest)

Recall 0.5 on attribute-on-instance calls; dead-code gate sound-but-conservative
(0 certificates on some repos); structural term unmeasurable on real repos by design
(oracle executes code); golden slices are subsystems, not full repos; chat needs a
model key for open-ended answers (tools answer deterministically regardless).

---

# APPENDIX — Exhaustive file inventory (for the architecture/directory redesign)

123 tracked files on `build/production-reengineering`, 162 on
`research/archimind-cpg-harness-20260925`. Untracked on disk: `PROJECT_STORY.md`
(1225-line user-side walkthrough of an older snapshot — not part of either branch),
`.env` (your Gemini key, gitignored), `data/` (sqlite, status JSONs, vector store,
gitignored), `experiments/soak.log` (gitignored), `experiments/fixtures/` (leftover
research-run outputs, untracked).

## A. Build branch — root (23 files)

| File | Purpose |
|---|---|
| `00_main.py` | Production entrypoint; re-exports `create_app` so gunicorn/Docker keep working |
| `app.py` | Flask app factory + all routes: `/`, `/workspace`, `/workspace/<ref>`, `/doc`, `/api/*` (analyze/status/preview/chat/history/golden/blast-radius/challenge), login/logout/signup, CSP headers, 429 concurrency guard |
| `auth.py` | Email/password user helpers (hashing, lookup) used by login/signup |
| `config.py` | Legacy env config (paths, models, limits); fixed schemeless-DATABASE_URL fallback |
| `models.py` | SQLAlchemy: `User`, `AnalysisLog` (rate limits + job states), `RepositoryHistory` |
| `oauth_utils.py` | Google OAuth blueprint (`/login/google`, callback), history cache + history queries |
| `services.py` | `RepositoryService` (fetch/clone/read), `VectorStoreService` (Pinecone/Chroma/local), `DocumentationService` (Gemini + local-heuristic handbook/diagrams/chat) |
| `worker.py` | Subprocess analysis pipeline: tarball-first ingest → index → retrieve → CPG ground → generate → per-diagram eval-optimizer repair → status JSON + DB |
| `requirements.txt` | Pinned runtime deps (Flask, LangGraph, Pinecone, tree-sitter≥0.25, tree-sitter-python, networkx, pydantic) |
| `requirements-dev.txt` | Lint/test tooling |
| `pyproject.toml` | ruff/black/mypy-strict configs |
| `Dockerfile` | Multi-stage build; gunicorn `app:create_app()` |
| `docker-compose.yml` / `docker-compose.pi.yml` | Prod + Raspberry Pi services |
| `.env.example` | Placeholder-only config template (incl. new MAX_CONCURRENT_JOBS, MERMAID_*, TARBALL_* vars) |
| `.gitignore` | Secrets, data/, logs, driver artifacts, caches |
| `.dockerignore` | Docker build context exclusions |
| `.coveragerc` | Coverage config |
| `README.md` | Project readme (OAuth vars table, troubleshooting) |
| `opencode.json` | OpenCode agent config for this repo |
| `setup.sh` | Bootstrap script |
| `single_sto.md` | This file |
| `.autoresearch-stop` | Sentinel stopping the dead research driver loop |

## B. Build branch — `src/` engine (29 files)

- `src/__init__.py`, `src/{config,ingestion,cpg,orchestration,governance,agentic,security,storage}/__init__.py` — package markers.
- `src/config/_00_settings.py` — Pydantic v2 `Settings` singleton (all engine env vars).
- `src/config/_01_constants.py` — extensions (py/ts/js), ignore dirs, 60MB/400-file caps, invariant ids, golden repo specs (PyTorch/OpenClaw/Requests subsystem slices).
- `src/ingestion/_00_tarball_client.py` — zero-clone tarball stream (64KB chunks, cap-guarded).
- `src/ingestion/_01_file_filter.py` — member keep/drop rules, basename decode with file cap.
- `src/ingestion/_02_subtree_client.py` — bounded contents-API subtree fetch for GB monorepos (per-dir + total caps, test-file exclusion, optional GITHUB_TOKEN).
- `src/cpg/_00_ts_ast.py` — tree-sitter Python+TS/JS symbol extractor: classes/bases/methods/functions/imports/**scoped** calls with receivers; stdlib-ast fallback; error-tolerant `parse_ok`.
- `src/cpg/_01_cpg_builder.py` — NetworkX DiGraph; per-scope CALLS resolution (self/this→owner, same-file wins, import narrowing, >3 ambiguous refused); INSTANTIATES/INHERITS/IMPORTS/DEFINES; SCC; **reverse** blast radius (callers/instantiators/subclasses); compact JSON artifact + loader.
- `src/cpg/_02_closure_gate.py` — out-of-corpus base witness; one-directional method withholding; `certified_dead` filter.
- `src/orchestration/_00_agent_state.py` — LangGraph `DiagramState` TypedDict.
- `src/orchestration/_01_eval_optimizer.py` — generate→validate→reflect cycle (cap 3); `validate_mermaid` (headers, bracket/paren balance, parens-in-`[]`, escaped-newline payloads, entity/hex-aware `#` rule); `normalize_mermaid` (unescape, subgraph quoting, paren→`#40;#41;`).
- `src/orchestration/_02_doc_synthesizer.py` — `cpg_context_block` grounding + `synthesize` wrapper.
- `src/orchestration/_03_cpg_diagrams.py` — valid-by-construction HLD (edge-driven package map + hub styling), LLD (class diagram + inheritance), flow (hottest cross-module call chain), deterministic chaptered handbook.
- `src/governance/_00_blast_radius.py` — `impact()` API helper (names, count, ms).
- `src/governance/_01_invariants.py` — presentation-isolation, acyclicity, domain-purity checks.
- `src/agentic/_00_cpg_tools.py` — deterministic assistant tools: `trace_symbol_impact`, `verify_architecture_rules`, `get_symbol_ast`.
- `src/agentic/_01_challenge.py` — Challenge-Me synthesis from zero-caller seams (schema + starter + failing test + hints).
- `src/security/_00_guardrail.py` — repo-scope prompt filter + exact trigger message.
- `src/security/_01_scrubber.py` — provider/model masking → "ArchiMind Neural Graph Core".
- `src/storage/_00_sqlite_cache.py` — SQLite JSON artifact store (golden.db legacy path).
- `src/storage/_01_golden_repos.py` — bundled fixture loader (`lru_cache`, traversal guard, `public_view` minus CPG blob, light card list).
- `src/storage/golden_fixtures/{pytorch,openclaw,requests}.json` — committed demos: stats, summary, handbook, 3 validated diagrams, invariants, repair_log, full CPG.

## C. Build branch — frontend (13 files)

- `templates/00_base.html` — doctype/head/viewport/fonts/variables + Jinja blocks.
- `templates/01_landing.html` — hero search (prefilled example), 3 demo cards with live counts, inline boot JS.
- `templates/02_studio.html` — topbar, 5 tabs, canvas+toolbar, reader+TOC, govern, challenge+tools, telemetry, docked assistant, FAB, backdrop.
- `templates/doc.html` — legacy full-handbook page (Engine label scrubbed, Gemini string removed).
- `templates/login.html` / `sign_up.html` — auth forms (viewport missing — known issue; personal UPI donate links removed).
- `static/css/00_variables.css` — slate/zinc tokens, `clamp()` type scale, drawer width.
- `static/css/01_landing.css` — hero/cards/mobile stacking (+btn/skeleton appended).
- `static/css/02_studio.css` — shell grid, tabs w/ fade, reader, governance, docked assistant/chat bubbles/tool badges/typing/chips/composer, pipeline steps, badges, drawers ≤1023px, icon-tabs ≤560px.
- `static/css/03_canvas.css` — glass toolbar/tabs, transform-only viewport, `.hit` blast highlight, empty/error states.
- `static/js/00_studio.js` — boot, golden/analysis load, diagram render + validator + code-graph fallback + note, chapter TOC, invariants, blast + highlight, chat + tools badges + chips, challenge hookup, telemetry/repair badges, polling progress, toolbar actions, `studio:tab` event.
- `static/js/01_pan_zoom.js` — wheel/drag/dblclick/pinch, fit clamped ≥0.55 for legibility, SVG export.
- `static/js/02_studio_tabs.js` — tab switching, chat/TOC drawers, backdrop/Escape/media-query reset.
- `static/js/03_challenge_ui.js` — challenge fetch/render/copy/next (random seam index).
- `static/doc.css` / `static/doc.js` — legacy doc page assets (untouched).

## D. Build branch — tests + scripts + docs + misc

- `tests/conftest.py` — sqlite test DB + safe env defaults; `tests/__init__.py`, `tests/{unit,integration,e2e}/__init__.py` — package markers.
- `tests/unit/test_cpg_engine.py` — extractor/builder/precision/self-bind/TS/blast/closure/roundtrip/invariants/eval-optimizer/tarball-URL/impact (13 tests).
- `tests/unit/test_ingestion_storage.py` — filter bounds, decode caps, URL rejection, cache roundtrip, **bundled-fixture validity incl. validator on all 9 diagrams + traversal-guard**.
- `tests/unit/test_agentic_security.py` — guardrail accept/reject, scrubber, tools, challenge schema.
- `tests/unit/test_mermaid_conformance.py` — the exact v11 failure samples locked (parens-in-label, escaped newlines, brackets, entities).
- `tests/integration/test_engine_resources.py` — CPG memory growth, 429 guard, golden list/detail, blast 400/404 + golden trace.
- `tests/integration/test_studio_security.py` — landing/studio render, chat guardrail/length/quota, challenge endpoint, no-leak assert.
- `tests/test_{app,config,services,worker,repository_service,integration}.py` — legacy suite (chat test updated to engine-label contract; config fallback bug fixed).
- `tests/e2e/test_studio_e2e.py` — landing cards, pytorch+openclaw × hld/lld/flow render asserts, 5 tabs, blast, challenge, guardrail chat, 4 viewports + hscroll asserts.
- `scripts/build_golden_cache.py` — subtree→CPG→diagrams→handbook→fixture writer (validator-gated, fails loud).
- `scripts/probe_diagrams.py` — real-mermaid-v11 render + screenshot probe for all fixtures.
- `scripts/soak_test.py` — paced load rig (rpm/duration/workers, backpressure cap, per-minute RSS, p50/p95/p99, PASS/FAIL verdict).
- `scripts/test_all.sh` — unit→integration→legacy→e2e→gates runner.
- `scripts/{run_local,run_worker,setup_local,test_local}.sh` — legacy local/dev runners.
- `scripts/{00_build_and_push_image,01_smoke_test_container,docker_preflight,deploy_pi,deploy_pi_build,install_pi_autostart_cron}.sh` — image/CI/Pi deploy plumbing.
- `scripts/02_convert_dot_to_drawio.py` — DOT→draw.io converter.
- `docs/profiling.md` — soak verdict + engine budgets + concurrency note.
- `docs/{README,AGENTS,CONTRIBUTING,RASPBERRY_PI_DEPLOYMENT}.md` — ops/contrib/Pi docs.
- `docs/diagrams/*` — `{flow,hld,lld,uml,use_cases}.{dot,drawio}` legacy design diagrams (+ one `.bkp`).
- `.github/workflows/test.yml` — CI; `.github/{README,FUNDING}.yml` — community files.

## E. Research branch-only files (162 total; shared product files identical to main-era)

State/loop: `autoresearch_research.md`, `.jsonl` (14 runs), `.ideas.md`, `_strategy_graph.jsonl`,
`-dashboard.md`, `.autoresearch-stop`; `experiments/worklog.md`; `equations.md` (42 rows);
`strategies.md`; `derivations.md`; `novelty_check_report.md`; `review_run7_n10.md`;
`papers/notes/{swe-bench-harness,reliable-graphrag-code}.md`.
Research engine (measurement instruments, NOT product code — superseded by `src/` above):
`src/00_cpg_static.py` (stdlib resolver), `01_dyn_oracle.py` (settrace oracle + event budgets),
`02_trace_promote.py` (held-out promotion, measured unsound), `03_metric_gate.py`,
`04_symbol_domain.py`, `05_export_boundary.py`, `06_protocol_driver.py` (manifest, killed on prior art),
`07_import_closure.py` (inheritance witness — the surviving idea, ported),
`08_interface_index.py` (≤1/2 bound enumeration), `09_resolution_price.py`,
`10_nonvacuity.py`, `11_name_refuter.py`, `12_escape_channel.py`, `13_oracle_channel.py`,
`14_ablation.py` (headroom law), `src/__init__.py`.
Harness: `scripts/run_auto_research.py` + `run_n{10..16}_*.py` measurers;
`experiments/run-*.log/.err` (runs 1–14 evidence); `experiments/fixtures/synthetic_{bad,cpg,promo,taint,protocol,protocol_driver,index,index_driver,escape,exports}_repo/`
(28 fixture files incl. `broken.py` syntax-error cases and `test_beta.py`).
Docs: `docs/{leaderboard,architecture,profiling}.md`, `docs/{hld,lld}.drawio`.
Research `tests/` = legacy flat suite only; research `templates/`+`static/` = pre-rebuild UI.
