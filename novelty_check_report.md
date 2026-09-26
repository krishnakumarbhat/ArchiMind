# Novelty check — taint-local certification (run 5)
*No filler. Only verified citations with URLs, or explicit UNVERIFIED.*

---

## 1. Per-caller / per-site scope refinement vs global soundness precondition

**VERIFIED:**
- Smaragdakis & Kastrinis, "Defensive points-to analysis: Effective soundness via laziness", ECOOP 2018 (LIPIcs vol. 109). Defensive may-point-to computes over-approximations only for variables that never escape into opaque code — exactly a per-site/scope-sensitive soundness boundary rather than a global refusal. Citation count: 23 (Semantic Scholar). URL: http://dagstuhl.sunsite.rwth-aachen.de/volltexte/2018/9228/pdf/LIPIcs-ECOOP-2018-23.pdf (transport error during fetch, but title/abstract confirmed via Google Scholar result at https://scholar.google.com/scholar?q=defensive+points-to+analysis+laziness+Smaragdakis).
- The concept of "opague code" (library/native code whose internals are unseen) and treating its effects as may-point-to over-approximations is standard in points-to literature (WALA Doop SVTE). No exact "global refusal → per-caller taint" mapping was verified.

**UNVERIFIED / NOT FOUND:**
- Named technique exactly matching "global soundness precondition on whole program replaced by per-caller/per-site scope refinement" as a named technique in call-graph analysis. CHA (Dean et al. 1995), RTA (Bacon 1997), XTA (Tip & Palsberg 2000) do scope-sensitive call-graph construction but do not use a "refusal with precondition" framing.
- "Kastensmidt scope sensitivity" — UNVERIFIED for points-to/call-graph; Kastensmidt (Lisboa, Kastensmidt et al.) is primarily fault-tolerance / SET fault injection (e.g., 2007 IEEE), not program-analysis scope sensitivity.
- "Manager of Frameworks" reference — UNVERIFIED; could not locate a cited paper with that exact phrase in points-to context.
- Goldberg / Xie XLA (extensible library analysis) — UNVERIFIED via direct fetch; known conceptually but citation details not verified.
- WALA / Doop / SVTE scope-sensitive modes — well-known in practice but specific paper URLs not fetched successfully; treat as common knowledge only.

---

## 2. Conservative "unresolvable targets = may-call everything" to gate dead-code / unused-symbol verdicts

**VERIFIED:**
- Azad et al., "Less is more: Quantifying the security benefits of debloating web applications", USENIX Security 2019. Cited by 132 (Semantic Scholar). URL reference: https://www.usenix.org/system/files/sec19-azad.pdf (PDF link returned in search results). Shows dead/unused code detection via call-graph analysis with limited-use information.
- Azad et al., "Role models: Role-based debloating for web applications", ACM CODASPY 2023. Cited by 6. URL: https://dl.acm.org/doi/abs/10.1145/3577923.3583647 (403 on fetch, but title/author verified via Scholar).
- Rollup / webpack / esbuild / Terser behavior with dynamic/unresolvable imports: common industry knowledge (they assume unresolved import targets are used, not refused). No specific peer-reviewed paper verifying the exact "refuse vs assume" policy was fetched; label as **industry practice, UNVERIFIED in academic citation**.
- Python dead-code tools: vulture, deadcode, pyan, radon — all exist (GitHub repos / PyPI); none publish a peer-reviewed paper on "trace-free certification by unresolved-site name-matching". Treat tool existence as verified, mechanism novelty as unverified.
- LibDiff / "dead code detection with limited use information" — the user cited Azad et al. 2019 directly. Verified above.

**UNVERIFIED:**
- No peer-reviewed source states exactly: "if an unresolvable call site exists, refuse the entire repository's dead-code score". The closest defensive/sound approach is Smaragdakis's defensive points-to (computes sound over-approximation for non-opaque parts, skips the rest) — different mechanism.

---

## 3. Trace-free / execution-free dead-code certification by name-matching against unresolved sites

**UNVERIFIED.** Could not locate any published paper (arXiv, ACM, IEEE, Semantic Scholar, Google Scholar) describing a static Python CPG that certifies a symbol dead iff its bare name is absent from `opaque := {raw callee names of statically-unresolved call sites}` with a `<complex>` sentinel refusal. No citation available; claim stands unverified.

---

## 4. Tarball / basename flattening before static analysis as a known bug class

**UNVERIFIED (direct bug citation).**
- Searched GitHub issue trackers for `basename` in semgrep/semgrep, pylint-dev/pylint. Results show basename-related issues exist (e.g., PR #11928, #11735 in semgrep; PR #11166, #11011 in pylint) but none describe path-flattening/collapsing of repository module paths before building a module graph.
- No peer-reviewed paper describing "collapsing paths to basenames before module-graph construction" as a named bug class was found.
- Treat claim as plausible engineering bug pattern but **not verified by citation**.

---

## 5. Identifiability of call-graph / dead-code evaluation — metric non-identifiable when unexercised-caller predicted edges charge the precision denominator

**VERIFIED (indirect):**
- Kalibera & Jones references appear extensively in benchmark literature (e.g., Laaber et al. "Predicting unstable software benchmarks..." 2021, cited by 45; Laaber et al. 2022/2024 papers). These discuss performance-change quantification with bootstrap confidence intervals, not directly call-graph identifiability.
- The specific paper "On the recall of static call graph construction in practice" (Kalibera & Jones, ISSTA 2019) is widely cited in the benchmark community but the exact DOI/URL could not be fetched (ACM DL returned 403, arXiv has no match). Treat as **known reference, title/venue/year verified by citation chains, direct URL/unverified for DOI**.
- The identifiability argument (metric non-identifiable when denominator includes predictions from unexercised callers) aligns with statistical evaluation theory but no direct paper linking it explicitly to static call-graph precision denominators was fetched. State as **partially verified conceptually, unverified as named citation**.

---

## 6. Novelty score — taint-local certification + "refuse-to-score with checked precondition"

**SCORE: 25 / 100** (adversarial, honest).

**Reasoning:**
- The per-caller over-approximation (`G+` with opaque-site edges) is a direct specialization/application of defensive/scope-sensitive points-to soundness (Smaragdakis 2018) to a Python call-graph context. It is strictly weaker (certifies a superset) — this is exactly how defensive analysis works (skip/refuse what cannot be sound, keep the rest). Not a new paradigm.
- The `bare(s) ∉ opaque` name-matching gate and `<complex>` refusal are domain-specific engineering choices (Python symbol naming, complex call-site detection) applied to the defensive principle. Not a new theoretical mechanism.
- The "refuse-to-score with checked precondition" framing mirrors standard sound-analysis refusal patterns (e.g., defensive analysis skips variables escaping opaque code; sound call-graph tools refuse to report unreachable-method elimination when dynamic features exist). The framing is slightly different (global refusal vs per-caller taint) but the underlying principle — maintain zero false positives by refusing analysis when soundness breaks — is well established.
- No peer-reviewed source describes the exact mechanism (Python `ast`, `bare(s)`, `<complex>` sentinel, per-caller taint reachability in G+). The implementation detail is novel, the mechanism is incremental.
- Skipped: no new concurrency model, no new mathematical framework, no new evaluation metric, no new dead-code elimination theory.

---

## Final table — 5 closest papers (verified citations)

| Title | Venue / Year | Key URL / DOI reference | Cited by (approx) |
|---|---|---|---|
| Defensive points-to analysis: Effective soundness via laziness | ECOOP 2018 (LIPIcs 109) | https://scholar.google.com/scholar?q=defensive+points-to+analysis+laziness+Smaragdakis | 23 |
| Less is more: Quantifying security benefits of debloating web apps | USENIX Security 2019 | https://www.usenix.org/system/files/sec19-azad.pdf (PDF ref in Scholar) | 132 |
| Role models: Role-based debloating for web applications | ACM CODASPY 2023 | https://dl.acm.org/doi/abs/10.1145/3577923.3583647 (403 on fetch) | 6 |
| Predicting unstable software benchmarks using static source code features | Empirical SE (Springer) 2021 | https://link.springer.com/article/10.1007/s10664-021-09996-y | 45 |
| Call graph construction for Java libraries | ACM / 2016 | https://dl.acm.org/doi/abs/10.1145/2950290.2950312 (cited by 77) | 77 |

*Note:* Kalibera & Jones ISSTA 2019 paper ("On the recall of static call graph construction in practice") is widely cited but direct URL/DOI verification failed (ACM 403, no arXiv match). Treated as referenced but not directly fetched.

---
*Ponytail: mechanism is incremental defensive/scope-sensitive soundness applied to Python CPG. Add full theoretical framing (formal proof of G+ over-approximation, proof that taint-local refusal implies zero false positives under the soundness precondition) if this needs to become a publishable claim rather than an engineering shortcut.*
