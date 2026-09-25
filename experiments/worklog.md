# Experiments Worklog: ArchiMind CPG Harness

**Topic:** Agentic Code Property Graph & Architecture Governance Harness | **Primary:** harness_score (0-100↑) | **Segment:** 0
**Branch:** research/archimind-cpg-harness-20260925 | **Started:** 2026-09-25

## Key Insights
- (setup) Baseline is linear RAG, not agentic: 3-node straight-edge graph, single-shot generation, no tools/validator/sandbox.
- (run 1) v0 on synthetic_bad_repo: harness_score=80.09 (validity 1.0, F1 0.68, dead 0.5, RAM 19.7MB). Regex edges already lose ~0.32 F1 vs AST truth — quantifies the CPG opportunity. Tiny-repo score is inflated; real repos (flask/requests) expected to drop F1 further and stress RAM.
- (model probe) Key valid (50 models listed). gemini-3.8-flash + 3.7-flash = persistent 503 (not provisioned for this key); gemini-2.5-flash = 404 (retired); text-embedding-004 = 404. Adopted: gen `gemini-3.1-flash-lite-preview` (repo default, generate OK), emb `gemini-embedding-001` (3072-dim, OK). Wired via gitignored `.env` only — never committed. Driver iterations should opportunistically re-probe `gemini-flash-latest`/3.8 and adopt if 200.

## Runs
### Run 1: v0_baseline_linear on synthetic_bad_repo — harness_score=80.09 (keep, BASELINE)
- Timestamp: 2026-09-25
- What changed: setup + `scripts/run_auto_research.py` + first benchmark execution.
- Math: equations.md #1 clamping verified in runner (max(0,·) on lat/ram sub-scores).
- Result: validity=1.0, F1=0.6827, blast=0.51ms, RAM=19.66MB, tokens=$0.008, dead=0.5 → score 80.09.
- Insight: baseline is the ceiling for naive matching; any real-world repo should score lower → headroom for v1/v2.
- Next: v1 evaluator-optimizer (Mermaid reflection) on broken-syntax fixture; v2 Tree-sitter CPG for F1→~1.0.

## Next Ideas
1. Run 1 (baseline): v0 linear on synthetic_bad_repo + flask tarball → record 6 metrics.
2. v1: add cyclic Mermaid validator+reflection (cap 3) → expect validity 0.x→1.0.
3. v2: pure Tree-sitter+NetworkX CPG, no vectors → expect F1↑, tokens→0, RAM?
4. Ablations per feature tree thereafter.

---
