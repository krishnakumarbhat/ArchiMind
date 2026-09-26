# Autoresearch Research Dashboard: archimind-cpg-harness

**Runs:** 14 | **Kept:** 14 | **Discarded:** 0 | **Crashed:** 0 (run 8 has no record — recovered inside run 9; iters 8–10 first stall + iters 7–9 second stall hit the 20-min watchdog with no state change)
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
| 12 | PENDING | 79.52/80 (same def) | keep | N14 eq. row 18 REFUTED; word "sound" withdrawn from 6 runs of counts; call-position carrier splits a fibre |
| 13 | PENDING | 79.52/80 (same def) | keep, L1 flagged VACUOUS | N15 truth-channel audit; L1 measured at 0 on 3/3 fixtures; 24/24 self-checks green over a vacuous law |
| 14 | PENDING | 79.52/80 (same def) | keep | N16 ablation: L1 non-vacuous (n_mfg=2), "strictly" RETRACTED, headroom law: truncation also PROTECTS the direction |

Head-to-head that matters: **v0 regex precision 0.2143 → CPG precision 1.0** (same fixture, same oracle, run 2). Honest costs: recall 0.5, resolution 0.5, root cause attribute-on-instance. Real-repo scale: flask/requests/sqlmodel/rich (≤333 files), peak RSS ≤72.63MB, $0 tokens. Score frozen runs 7–14 by construction (dead term unscored) — work moved to soundness proofs + impossibility result (≤1/2 bound, UNVERIFIED-novel).

## Runs 12-14 in one line each

- **Run 12 (N14)** — the loop's own soundness adjective is withdrawn: row 18's lemma is false, witnessed by `getattr(o, "".join(["lo","ad"]))()`, giving 1 executed false positive. Counts stand; the claim does not.
- **Run 13 (N15)** — L1 is published and then measured at zero on every fixture. Vacuous truth, cause located in the run's own driver. L1b/L2 and the call-counter falsification survive and are sound.
- **Run 14 (N16)** — the ablation. L1 becomes non-vacuous, "strictly" is retracted in favour of an iff, and the new headroom law says an incomplete oracle both manufactures false positives and shields the direction against invention.

**The through-line across all three:** the loop stopped trusting its own instruments. Run 12 found a published claim that was false, run 13 found a published law that was untested, and run 14 found a crash in the instrument plus a verdict string that contradicted its own numbers. **N8 blocked for the seventh consecutive run; N6 deferred. Next: N17, the near-complete-oracle regime where headroom is small enough for one invention to reverse L1.**
