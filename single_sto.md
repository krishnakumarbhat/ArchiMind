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
