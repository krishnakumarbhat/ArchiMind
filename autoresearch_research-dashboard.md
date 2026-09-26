# Autoresearch Research Dashboard: archimind-cpg-harness

**Runs:** 10 | **Kept:** 10 | **Discarded:** 0 | **Crashed:** 0 (run 8 has no record — recovered inside run 9; iters 8–10 first stall + iters 7–9 second stall hit the 20-min watchdog with no state change)
**Baseline:** harness_score: 80.09pts (#1, static-F1 def)
**Best:** harness_score: 86.23pts (#2, dynamic-oracle-v1) — **NOT comparable across metric defs (4 defs used). Decision-grade numbers are the within-run head-to-heads.**

| # | commit | harness_score | status | description |
|---|--------|---------------|--------|-------------|
| 1 | e72fed2 | 80.09pts | keep | baseline: v0 regex edges vs AST truth (F1 0.6827) |
| 2 | b4af665 | 86.23pts (def change) | keep | v2 stdlib-ast CPG + sys.settrace oracle; v0 prec 0.2143 vs CPG 1.0 |
| 3 | ee2d604 | 66.23pts (def change) | keep | v3 trace-informed promotion, held-out: prec 1.0 / recall 0.7143 |
| 4 | 9c98ed3 | 66.21pts (def change) | keep | metric repair certified-dead-v3; run-1 F1 invalidated as self-fulfilling |
| 5 | 39b403d | 79.56/80 (def change) | keep | N7 symbol-domain hygiene; fixture 0 FP / 0 FN |
| 6 | 93ef187 | 79.52/80 (same def) | keep | N9 consumer-boundary gate; third self-refutation |
| 7 | 6547cb9 | 79.52/80 (same def) | keep | N10 killed on prior art (Vulture whitelist); inheritance witness closes 4/4 residuals |
| 9 | 7b1c36c | 79.52/80 (same def) | keep | N11 bound derived not asserted (19,683 gates enumerated, max acc 0.5) + 2 self-retractions |
| 10 | 17d7dce | 79.52/80 (same def) | keep | N12 law retraction + carrier enumeration; parity bit-identical to run 7 |
| 11 | db0e6ef | 79.52/80 (same def) | keep | N13 non-executing adjudicator refuted twice; vacuity on 2014 real edges |

Head-to-head that matters: **v0 regex precision 0.2143 → CPG precision 1.0** (same fixture, same oracle, run 2). Honest costs: recall 0.5, resolution 0.5, root cause attribute-on-instance. Real-repo scale: flask/requests/sqlmodel/rich (≤333 files), peak RSS ≤72.63MB, $0 tokens. Score frozen runs 7–11 by construction (dead term unscored) — work moved to soundness proofs + impossibility result (≤1/2 bound, UNVERIFIED-novel).
