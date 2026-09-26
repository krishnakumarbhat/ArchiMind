# Architecture: ArchiMind Agentic CPG & Governance Harness

## 1. Two systems in one repo

- **Product** (`app.py`, `worker.py`, `services.py`, `models.py`, `config.py`): Flask + LangGraph
  retrieval (`select_files → collect_chunks → render_context`, `services.py:1147-1156`) +
  single-shot Gemini Mermaid synthesis. Linear RAG: ingest → chunk → embed → generate.
- **Research harness** (`src/00–14_*.py`, `scripts/run_auto_research.py`, `tests/benchmarks/`,
  `experiments/fixtures/`): the subject of runs 1–14. Deterministic static CPG audited by
  an independent dynamic oracle, with a soundness-gated dead-code certifier. Zero model
  calls in the measurement loop ($0.00 tokens on every run).

## 2. Pipeline (score-bearing path)

```
GitHub tarball (streamed, ≤60MB, tests/vendor/media dropped)
  → file filter (≤400 files, ≤200KB each, io.BytesIO chunking)
  → 00_cpg_static: stdlib-ast symbol resolution → CALLS / IMPORTS / INHERITS edges,
     entry points, Tarjan SCC, BFS blast radius, bitset reachability closure
  → 01_dyn_oracle: sys.settrace harness with auto-generated dummy-arg drivers,
     deterministic DEFAULT_EVENT_BUDGET (run 12) instead of wall clock (run 13 vacuous)
  → 03_metric_gate: precision/recall vs oracle + identifiability gate (eq. row 17);
     dead term UNSCORED since run 4 (certified-dead-v3) — reported as certified SET
  → 04_symbol_domain → 05_export_boundary → 07_import_closure: layered withholding
     (dunder, string-only, star-import closure, out-of-corpus base edge)
  → 08–14: impossibility instrumentation (interface index, resolution price,
     non-vacuity sweep, name refuter, escape/oracle channels, budget ablation)
  → experiments/run-N.log + JSONL + worklog + leaderboard
```

## 3. Key design decisions (all measured, none asserted)

1. **Oracle independence.** A second static parse shares every blind spot of the first
   (both miss constructor-chained calls) — so ground truth is *execution* (`sys.settrace`),
   never re-parsing. `01_dyn_oracle` docstring states the argument.
2. **Deterministic cuts.** Wall-clock bounds never expire on fixtures (run 13: L1 vacuous);
   SIGALRM is non-deterministic across processes (4/10/4/4/4 dispatches). Event-count
   budgets are a function of input alone (run 12/14).
3. **Soundness by withholding, one direction only.** Withholding a verdict cannot create a
   false positive; it also cannot rescue the unblocking direction (run 12: veto on the
   consumer module, candidate in `witnesses` — sound and useless there).
4. **No name lists.** Protocol manifests and convention lists are Vulture whitelists under
   a new noun (run 7 prior-art kill, `vulture#430` bare-name bug rediscovered). The surviving
   witness is structural: the out-of-corpus **inheritance edge** (`07_import_closure`).
5. **Metric parsimony.** Four metric defs across 14 runs; every change logged with
   `metric_def` tags and a same-fixture parity re-run. Scores across defs are incomparable —
   the leaderboard reports head-to-heads, not a single column.

## 4. Proven limits (shipped as findings, not failures)

- Recall 0.5 / resolution 0.5: attribute-on-instance calls invisible to static resolution.
- Any deterministic in-corpus-only gate scores ≤ 1/2 on the discriminating pair
  (`alpha.T.process_literal_param` LIVE vs `alpha._fixture_dead_plain` DEAD, identical
  evidence vectors) — `getattr`-by-protocol dispatch is irreducibly external (N11, UNVERIFIED-novel framing).
- L1 headroom law (run 14): truncation manufactures FPs *and* shields against invention;
  direction reverses iff `headroom = |D∩T| − |D∩O| < 0`. No source found.
- Structural term unmeasurable on real repos by design (oracle executes code) — N8 blocked 7 runs.

## 5. Constraints (verified every run)

Peak RSS ≤ 72.63 MB (ceiling 380) · $0 tokens · no in-RAM vector DB · no local LLM ·
no `git clone` · `.env` gitignored · ruff/mypy/flake8(E9,F63,F7,F82) + per-module
assert-based `_self_check()` (14 modules, all green at close-out).
