# Experiments Worklog: ArchiMind CPG Harness

**Topic:** Agentic Code Property Graph & Architecture Governance Harness | **Primary:** harness_score (0-100↑) | **Segment:** 0
**Branch:** research/archimind-cpg-harness-20260925 | **Started:** 2026-09-25

## Key Insights
- (setup) Baseline is linear RAG, not agentic: 3-node straight-edge graph, single-shot generation, no tools/validator/sandbox.
- (run 1) v0 on synthetic_bad_repo: harness_score=80.09 (validity 1.0, F1 0.68, dead 0.5, RAM 19.7MB). Regex edges already lose ~0.32 F1 vs AST truth — quantifies the CPG opportunity. Tiny-repo score is inflated; real repos (flask/requests) expected to drop F1 further and stress RAM.
- (run 1 caveat, discovered run 2) That 0.68 F1 is **not a quality signal**. v0's regex and the "ground truth" were the same blind technique on the same text; v0 has no caller/callee representation at all, so it was only ever scored in its own degenerate vocabulary.
- (model probe) Key valid (50 models listed). gemini-3.8-flash + 3.7-flash = persistent 503 (not provisioned for this key); gemini-2.5-flash = 404 (retired); text-embedding-004 = 404. Adopted: gen `gemini-3.1-flash-lite-preview` (repo default, generate OK), emb `gemini-embedding-001` (3072-dim, OK). Wired via gitignored `.env` only — never committed. Driver iterations should opportunistically re-probe `gemini-flash-latest`/3.8 and adopt if 200.
- (run 2) Potency re-ranking: **v1 (N2) has zero headroom** — v0 already scores `mermaid_validity_rate=1.0`, so reflection buys 0 of the 100 points and spends tokens. v2 (N3) was the only frontier node attacking the 50 points that are actually weak. N3 expanded; N2 left unexpanded with a recorded reason rather than quietly skipped.
- (run 2) A *second static parse is not an oracle*. Scoring an `ast`-based predictor against an `ast`-based truth returns 1.0 while both miss the identical edges. Any "CPG F1" number in this harness computed that way is unmeasurable by construction.
- (run 2) Dynamic oracle (`sys.settrace` + auto-harness) is the first independent ground truth here, and it immediately paid for itself by catching a real bug in my own CPG (eq. row 6: class-instantiation edges dispatched as `Cls.__init__`, not `Cls`) that no amount of static review had flagged.
- (run 2) One root cause explains every remaining weakness: **attribute-on-instance calls** (`self.s.query(uid)`). It caps `cpg_resolution_rate` at 0.5, `struct_recall_dyn` at 0.5, and drags `dead_code_acc` to 0.333. Fixing that one pattern is worth more than any remaining score-shaping.
- (run 2) Python 3.10 has no `code.co_qualname`, so a raw trace yields `fetch`, not `UserRepo.fetch`. Class identity has to be recovered from a code-object index built out of the repo's own modules, or the oracle and the CPG end up speaking different vocabularies and the comparison is meaningless.
- (run 2) `synthetic_bad_repo` has a **circular import** (repo→routes→repo) and cannot be imported at all, so it is unusable as a dynamic-oracle subject. Its `import routes` is also dead code — the fixture was hiding a finding. New acyclic `synthetic_cpg_repo` added; the old fixture is untouched so run-1 numbers stay comparable.

## Runs
### Run 1: v0_baseline_linear on synthetic_bad_repo — harness_score=80.09 (keep, BASELINE)
- Timestamp: 2026-09-25
- What changed: setup + `scripts/run_auto_research.py` + first benchmark execution.
- Math: equations.md #1 clamping verified in runner (max(0,·) on lat/ram sub-scores).
- Result: validity=1.0, F1=0.6827, blast=0.51ms, RAM=19.66MB, tokens=$0.008, dead=0.5 → score 80.09.
- Insight: baseline is the ceiling for naive matching; any real-world repo should score lower → headroom for v1/v2.
- Next: v1 evaluator-optimizer (Mermaid reflection) on broken-syntax fixture; v2 Tree-sitter CPG for F1→~1.0.

### Run 2: v2 static CPG validated by a dynamic oracle — harness_score=86.23 (keep, METRIC CORRECTION)
- Timestamp: 2026-09-25 | Evidence: `experiments/run-2.log` | Code: `src/00_cpg_static.py`, `src/01_dyn_oracle.py`
- What changed: added a stdlib-`ast` symbol-resolved CPG (call/import edges, Tarjan SCC, entry-point reachability, BFS blast radius) and a `sys.settrace` dynamic oracle with an auto-generated dummy-arg harness. Added `--pair` so v0 and v2 are scored on the same fixture by the same oracle. Added fixture `synthetic_cpg_repo` (acyclic; run-1 fixture left untouched).
- **Metric definition changed: `metric_def: dynamic-oracle-v1`. The 86.23 is NOT comparable to run 1's 80.09.** v2's structural term is oracle precision, v0's was static F1. The score column is only comparable within one definition.
- Reproducibility: v0 re-run on the run-1 fixture returns `structural_f1_static=0.6827`, `dead=0.5`, `blast=0.51ms` — identical to run 1. Score moves 80.09→80.06 only via `peak_ram_mb` (19.66→21.84MB, the two extra imported modules); RSS is process-wide and cumulative. Metric parity confirmed, not assumed.
- Head-to-head (the decision-grade result, same fixture, same oracle, same coarse vocabulary):
  - **v0 regex: coarse precision 0.2143** (3 of 14 predicted callees real)
  - **v2 CPG: coarse precision 1.0** (2 of 2 real), fine-grained precision 1.0, `struct_false_edges=[]`
  - v0 emits 14 candidate callees for 4 real ones; the CPG emits 2 and every one is real. A governance gate that invents a coupling is worse than a silent one.
- Where v2 is honestly worse: `struct_recall_dyn=0.5`, `cpg_resolution_rate=0.5`, `dead_code_acc=0.3333` (v0: 0.5). All one root cause — `self.s.query(uid)` attribute-on-instance calls are invisible to static resolution. The CPG flagged them in `cpg_unresolved`, which is the correct behaviour for a resolver that refuses to guess.
- Hard constraints: peak RSS 22.4MB (≤380 ✓), token cost $0.00 (no model in the loop ✓), no in-RAM vector DB ✓, no local LLM ✓, no clone ✓, secrets not committed (`.env` gitignored, verified) ✓.
- Toolchain: `ruff` clean, `mypy` clean, `flake8` clean; both modules ship an assert-based `_self_check()` that fails if resolution, dead-code, blast radius, SCC or the bitset/BFS closure cross-check regress.
- Insight: an *accuracy over a prediction set* (`dead_acc = |confirmed ∩ predicted|/|predicted|`) is the only dead-code metric that does not reward guessing "everything is dead". Reporting 0.3333 against v0's hardcoded 0.5 is the honest trade, and it is what makes the recall number trustworthy.
- Next: v3 trace-informed edge promotion — use the oracle's missed set to promote statically-unresolved attribute-on-instance edges, then re-measure. This is the highest-potential node; 30 pts of F1 are gated behind it.

## Next Ideas
1. **v3 (highest potential): trace-informed CPG repair.** For each `cpg_unresolved` entry, bind it to a trace dispatch to promote a static edge; expect `struct_recall_dyn` 0.5→≥0.8 and `dead_code_acc` 0.333→≥0.6.
2. Oracle completeness bound: report `|D| / |T|` so the incomplete-oracle bias (eq. row 4) is quantified rather than assumed. Needs a third reference — instrumented `coverage` on a repo whose true edge set is enumerable.
3. v1 evaluator-optimizer: only worth running against a fixture that actually *fails* Mermaid validation; on this fixture it is provably worth 0 points.
4. Scale the paired run to a real tarball repo (flask/requests) — RAM and resolution rate on real code are still unmeasured. Dynamic oracle must stay off untrusted repos (it executes code); static-only for those.
5. Ablations: CPG±, oracle on/off (measures what the oracle is worth to the *metric*, not the pipeline), dunder-exempt on/off.
