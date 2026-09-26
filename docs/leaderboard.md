# Leaderboard: ArchiMind CPG Harness Variations

> **Metric-definition warning.** The loop changed the scoring definition 4 times as it
> found each predecessor self-fulfilling. Cross-row `harness_score` comparisons are
> invalid except within one definition. The decision-grade results are the **same-fixture,
> same-oracle head-to-heads** inside a single run. Evidence: `experiments/run-N.log`.

## Standing table (score-bearing fixture per row)

| Run | Variation | Metric def | Score | Precision | Recall | Dead-code | Evidence |
|-----|-----------|------------|-------|-----------|--------|-----------|----------|
| 1 | v0_baseline_linear (regex edges) | static-F1 | 80.09 | F1 0.6827 | — | 0.5 (hardcoded) | run-1.log |
| 2 | v2 stdlib-ast CPG + dyn oracle | dynamic-oracle-v1 | 86.23 | **1.0** (v0: 0.2143) | 0.5 | 0.3333 | run-2.log |
| 3 | v3 trace-informed promotion (mode B) | heldout-v2 | 66.23 | heldout 1.0 | heldout 0.7143 | 0.0–0.3333 | run-3 |
| 4 | v3 re-scored | certified-dead-v3 | 66.21 | evaluable 1.0 (5 edges) | 0.7143 | 0.0 strict | run-4 |
| 5 | N7 symbol-domain hygiene | unreferenced-v4 (/80) | 79.56 | 1.0 | 0.5 | 2 certified, 0 FP/0 FN | run-5 |
| 6 | N9 consumer-boundary gate | unreferenced-v4 | 79.52 | 1.0 | 0.5 | set shrinks, sound | run-6 |
| 7 | N10 inheritance witness (manifest killed on prior art) | unreferenced-v4 | 79.52 | 1.0 | 0.5 | 21 real-repo certs (−9) | run-7 |
| 9 | N11 derived ≤1/2 bound (19,683 gates) | unreferenced-v4 | 79.52 | 1.0 | 0.5 | unchanged | run-9 |
| 10 | N12 retractions + carriers | unreferenced-v4 | 79.52 | 1.0 | 0.5 | unchanged | run-10 |
| 11 | N13 adjudicator (refuted) | unreferenced-v4 | 79.52 | 1.0 | 0.5 | unchanged | run-11 |

## Real-repo scale (tarball ingestion, static-only — oracle executes code, never run on untrusted repos)

| Repo | Corpus files | Predicted dead (run 7) | Certified run 6 → 7 | Resolution notes |
|------|--------------|------------------------|---------------------|------------------|
| pallets/flask | 83 | 204 | 4 → 4 | 19 witnessed classes, 0 removed |
| psf/requests | 37 | 110 | 22 → 17 | 5 removed = real out-of-corpus subclass methods |
| tiangolo/sqlmodel | 333 | 246 | 3 → 0 | sound-but-useless regime |
| Textualize/rich | 213 | 452 | 1 → 0 | RichHandler.emit withheld via base edge |

## Hard constraints (all runs)

- Peak RSS ≤ 72.63 MB worst case (limit 380) ✓
- Token cost $0.00 — no model in the measurement loop ✓
- No in-RAM vector DB, no local LLM, no `git clone` (tarball stream) ✓
- Secrets: `.env` gitignored, verified each run ✓

## Prior-art ledger

- **PyCG** (MSR 2021, ~99.2% prec / ~69.9% rec) — the true baseline; loop cited it only at run 6.
- **Vulture** — global bare-name counting = run 6's `R(m)`; whitelist = killed N10; issues #417/#430 request the per-module fix run 6 proved unsound.
- **N11 ≤1/2 impossibility framing** — UNVERIFIED-novel (rests on Reiter closed-world + Cook–Goodwin undecidability, unchecked).
- **Vulture README** (VERIFIED run 14) — documents the `getattr` false positive and claims NO soundness, so run 12's retraction withdraws *this loop's* adjective, not a published claim.
- **Headroom law (run 14)** — NO SOURCE FOUND: that an incomplete oracle both manufactures false positives and shields the upper-bound direction against invention. The only element of runs 12–14 carried at novelty > standard.
- L1–L3 (run 13) — accepted by the reviewing sub-agent as **restated measurement theory**; a reviewer would say so.
- Novelty peak 46/100 (run 14, up from 34) → engineering track, no paper.

## Conclusion

Ship v2 CPG + N7/N9/N10 gate stack: precision 1.0, zero false positives on all fixtures,
sound-by-construction withholding on real repos. Do not ship trace promotion (v3) or name
manifests (N10-as-proposed): measured unsound. Open problem: recall stuck at 0.5
(attribute-on-instance); structural term unmeasurable on real repos by design.

**Runs 12–14 corrected the record rather than the score.** Run 12 refuted eq. row 18 and withdrew the
word *sound* from six runs of certification counts (the counts stand). Run 13 published L1 and measured
it at zero on every fixture — a vacuous law with 24/24 green self-checks. Run 14 built the missing
ablation, made L1 non-vacuous, retracted *strictly* in favour of the iff `measured − true =
|predicted & omitted|`, and established the headroom law. A crash in the oracle's setup guard and a
verdict string that read `REVERSES` beside `direction_survives = True` were both found by running the
experiment and are fixed. N8 blocked for the seventh consecutive run; N6 deferred.
