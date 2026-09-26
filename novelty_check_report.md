# Novelty Check — Run 6 / node N9 (consumer-boundary dead-code gate)

**Method:** adversarial sub-agent with web search across arXiv, Semantic Scholar, Google Scholar,
Papers with Code, OpenReview and GitHub. Minimum 10 queries. Instructed to be adversarial and told
explicitly that a wrong "novel" claim is worse than a low score, because the loop retains retracted
results. Sub-claim verdicts and the sub-agent's own score are reproduced below; **no citation here was
written by me without the sub-agent fetching it**, and anything it could not verify is marked
UNVERIFIED rather than asserted.

**Verdict: 35/100 → engineering track, no LaTeX paper.**

---

## 1. Prior art I had MISSED, found by the checker rather than by me

| Work | Why it matters here | Verified detail |
|---|---|---|
| **PyCG** — Salis, Sotiropoulos, Louridas, Spinellis, Mitropoulos, *IEEE/ACM MSR 2021*, [arXiv:2103.00587](https://arxiv.org/abs/2103.00587) | This is the real published Python CPG baseline and **this loop never cited it** across six runs while building a Python CPG and writing "nobody combines all four" claims in `autoresearch_research.md`. Precision ~99.2%, recall ~69.9% on its own benchmark. | Abstract + ~153 Google Scholar citations confirmed. Star-import / `__all__` / nested-decorator handling **UNVERIFIED** — not in the abstract. |
| **Vulture** — `jendrikseipp/vulture`, MIT, ~4.8k stars | Already implements the **same primitive** as this loop's `occ[]`: a global bare-name reference count. Its README states outright: *"This analysis ignores scopes and only takes object names into account."* That sentence is the exact scoping limitation eq. row 16 measured, declared by the tool itself. | README fetched in full. Confidence tiers 60–100%, whitelists, `--ignore-decorators`, `--ignore-names`. **No `__all__` support, no entry-point seeding, no per-module scoping documented.** |
| **`dead`** — `asottile/dead` v2.1.0 | Second independent confirmation that the global-name-scan approach is standard: AST parse plus a repo-wide definition/reference search. Documented false positives: interfaces, metaclasses. | No wildcard/re-export node; no `__all__` handling. |
| **Grimp**, **modulegraph**, **import-linter** | Import-graph builders. Confirmed they model imports but **feed nothing into dead-code reachability seeding**. | Grimp v3.17 docs. |

## 2. The seven questions, answered

| # | Question | Answer |
|---|---|---|
| 1 | Does `from m import *` bind names the importer never spells? | **Yes, as a statement about bindings** — and this loop **measured that it is irrelevant to dispatches**. Every way of calling through the binding spells the name; the only nameless route is `vars()`/`dir()` reflection, which is the runtime-assembly ceiling run 5 already named. Vulture and `dead` emit no wildcard/re-export node, so neither *can* see these references — but neither is thereby unsound, for the reason above. **No published numeric FP rate attributable to star imports exists (UNVERIFIED).** |
| 2 | PyCG limitations | Inter-procedural assignment-relation analysis across modules, generators, closures, multiple inheritance. Precision ~99.2% / recall ~69.9%. Star-import, `__all__`, decorator and C-extension handling **UNVERIFIED**. |
| 3 | Vulture `__all__` / FP rate | No `__all__` support, no entry-point seeding, no per-module scoping. **Published peer-reviewed FP/FN numbers on real repos: UNVERIFIED** — no benchmark found. |
| 4 | "Unreferenced in corpus" vs "dead" | Vulture and `dead` both conflate them and handle the library-API case with **manual whitelists** (`whitelist.py`, `# dead: disable`, `--ignore-decorators`). Entry-point/re-export seeding exists for *dependency* analysis (modulegraph, import-linter, grimp), never for dead-code reachability. **A peer-reviewed paper naming the two categories for Python: UNVERIFIED.** |
| 5 | Entry-point-seeded reachability in a Python dead-code tool | **Verified absence.** No tool found seeds reachability from `entry_points` / `console_scripts` / `__init__.py` re-exports. This is a genuine gap — and it is the gap `src/05_export_boundary.py` closes, in weakened form. |
| 6 | Per-module vs global occurrence counting | Vulture: global, explicitly scope-blind. `dead`: repo-wide name match, no module scoping. **No tool found uses qualified-symbol occurrence scoping for dead-code detection.** |
| 7 | Star-import handling across tools | Vulture / `dead` / Grimp: **no** wildcard node, references must be spelled (verified negative). PyCG: **UNVERIFIED**. |

## 3. Closest prior art to N9, and exactly where it stops

- **Overlaps:** Vulture's global bare-name reference count is the same primitive as `occ[]`, and its
  "100% confidence" tier is the same claim as run 5's `occ == 1` certificate. My tokenizer counts
  identifier-shaped **string** literals as well, which is a real refinement of the same idea.
- **Does not overlap:** the explicit four-way partition separating *certified dead* from *publicly
  exported* from *externally driven* from *blocked by mention*; and the driver-convention manifest
  (`test_*` / `time_*` / `track_*`, `benchmarks/` / `docs_src/` / `scripts/`), which no tool
  expresses. Every existing tool handles the library-API case by **suppression** (a hand-maintained
  whitelist); this loop derives it from a **declared convention**.

## 4. Per-sub-claim verdicts

| Sub-claim | Verdict | Deciding evidence |
|---|---|---|
| (a) star-import soundness hole in an occurrence-count rule | **INCREMENTAL, and empirically false** | Python star-import semantics are language basics; and this loop's own fixture showed the hole does not exist, because dispatch requires naming the bound name. A "hole" that is not a hole is worth less than a clarification. |
| (b) consumer-boundary / externally-driven liveness-witness category | **NOVEL within the Python dead-code literature; taxonomic overall** | Verified: no fetched tool (Vulture, `dead`, PyCG, Grimp, modulegraph) classifies "exported or externally driven but unreferenced inside the corpus" automatically. But it is a *classification layer over the same occurrence-count oracle*, not a new proof technique or a new measurement. |
| (c) per-module-scoped occurrence counting | **PRIOR-ART-STANDARD** | Module scoping is standard static-analysis hygiene (PyCG's inter-procedural module analysis, WALA/Closure package scoping). Applied to a dead-code occurrence count it is a refinement — and one this loop **measured to be unsound**, which the sub-agent could not have known. |

## 5. Why a reviewer would call this incremental

> A reviewer fluent with Vulture and PyCG would observe that run 6 takes a known conservative
> heuristic — a global bare-name dead-code count — and adds three well-understood adjustments: handle
> `import *` (language semantics), scope counts per module (standard hygiene), and stop reporting
> exported API as dead (engineering practice, normally handled by a whitelist). None introduces a new
> proof technique, oracle, or soundness argument. The headline mechanisms turned out to be **wrong**:
> the star-import hole does not exist, the per-module fix is unsound, and the `__all__` direction is
> impossible. What survives — a driver-convention manifest and a four-way partition — is a reporting
> improvement plus one genuinely new negative result, the `R(m)` over-approximation theorem, which
> explains *why* the conservatism is irreducible rather than proposing to reduce it.

## 6. UNVERIFIED-novel — logged as such, deliberately

Two items in run 6 were **not found in any source** and are recorded as *unverified-novel* rather
than novel, because absence of search results is not evidence of absence:

1. **The `R(m)` over-approximation theorem** (eq. row 22): a dispatch to `m.n` from `P` requires `P`
   to spell `n` **and** `P ∈ R(m)`; `R(m) = all modules` is the identity over-approximation and the
   cheapest sound choice, so the measured 2–20% certification rate is the *price of soundness*.
   The framing as a general theorem over `R` is mine; the underlying fact that call-graph
   reachability is undecidable/aliasing-bound is textbook.
2. **The driver-convention manifest** as a *declared, auditable* input to a sound dead-code gate,
   with the one-directional argument that withholding cannot create a false positive. The closest
   prior art found — Vulture's `--ignore-decorators` and whitelists — reaches the same practical
   outcome by user-maintained suppression rather than by a declared convention, and neither states
   the soundness direction.

## 7. Decision

35/100. Below the loop's paper threshold (the run-2 idea scored 42 and was already engineering-track
only). **No LaTeX paper.** Engineering track: the deliverable is the measured retraction of the
node's own hypothesis, the `R(m)` theorem in `equations.md` row 22, the sign-corrected
external-driver withholding clause in `src/05_export_boundary.py`, and the 48-of-75 real-repo
certificate removal in `experiments/run-6.log`.

---

## Run 7 — adversarial novelty check (the check found the kill)

**N10's protocol manifest: PRIOR ART, killed before implementation.** Vulture's documented remedy for a false positive is a hand-maintained external list: [vulture.readthedocs.io — "Whitelists"](https://vulture.readthedocs.io/en/stable/whitelists.html) instructs users to add used code to a Python module on the scanned path, and the package ships `vulture/whitelists/` for common packages. A declared protocol manifest is that mechanism under a different noun. Its matching bug is on the record: [jendrikseipp/vulture#430](https://github.com/jendrikseipp/vulture/issues/430) — "Whitelist matches by bare identifier name only … `used_names` is a single global set of bare strings … Any symbol, in any file, with the same name is permanently shielded." Run 6's retracted `setup_`/`teardown_` list was already a second instance; N10 proposed a third and larger one.

**Run 6's `R(m)` theorem: prior art CONFIRMED, from Vulture's own source.** [vulture/core.py](https://github.com/jendrikseipp/vulture/blob/main/vulture/core.py) keeps one global `used_names` set of bare strings — this *is* `R(m) = all modules`, the identity over-approximation of eq. row 22. [Issue #417](https://github.com/jendrikseipp/vulture/pull/417) and #430 both request the per-module scoping that run 6 **proved unsound** (it certifies `lib.legacy.legacy_star_target`, which `app.main()` calls). This is the first prior-art *confirmation* in the loop's history, and it was found by the checker rather than by me.

**N10's H1, measured: REFUTED_UNSOUND.** `synthetic_protocol_repo`, written-down truth, **executed** out-of-corpus driver. `PROTOCOL_NAMES` certifies `alpha.T.process_literal_param`, which the driver dispatches — precision 0.0, 1 false positive. An open list withholds only what it lists, so an unlisted protocol name is certified: it fails **unsoundly**, strictly worse than run 6's over-blocking conventions.

**N11 (impossibility result): NOVEL in framing, prior art in ingredients — UNVERIFIED, flagged.** The 1/2 bound and the "reflection interface is irreducibly external" formulation were found in **no** source. Ingredients that plausibly already contain it: the **closed-world assumption** (Reiter) in knowledge bases — the same argument that absence of evidence is not evidence of absence; **Cook & Goodwin (1986)** on the undecidability of dynamic dispatch; reflection analysis in Python static analysis (Pysa, TamiFlex). **I did not verify any of these three and a human must.** The loop has now twice been wrong about a literature it had not read (run 6: PyCG uncited for six runs; run 7: Vulture's whitelist reinvented three times), so the honest prior on my own novelty verdicts is low.

---

## Run 9 — adversarial novelty check on the N11 claim set (recovered work)

**Method.** Two sub-agents in parallel, on separate providers. One told to find prior art that
**kills** the claim set; one told to assume the mathematics was **wrong** and find the error.
Both were given the claim set and nothing else about the loop's reasoning. The second found the
defect that mattered; see eq. row 30. Full detail: `equations.md` rows 28–31, `experiments/run-9-n11-reproduce.log`.

### Novelty: 46 → **15/100**. Engineering track, no LaTeX paper. Lowest in the loop's history.

| # | Claim | Verdict | Basis |
|---|---|---|---|
| 1 | Any deterministic in-corpus gate scores ≤ 1/2 on the protocol class | **PRIOR-ART-KILL** | Rice 1953; Reiter 1978 (closed-world assumption); Cook & Goodwin, ECOOP 1999; PyCG arXiv:2103.00587 |
| 2 | The achievable (certified, accuracy) set is a two-point dichotomy | **INCREMENTAL** | the CWA binary; the 2560-gate enumeration is implementation detail |
| 3 | `accuracy = (n_dead + j)/\|C\|`, one bit worth `1/\|C\|` | **PRIOR-ART-KILL as concept**, UNVERIFIED-NOVEL as a named law | linear arithmetic; **and after eq. row 30 it is a law about an unsound gate family** |
| 4 | Only a per-symbol declaration lifts the bound; that shape is an allowlist | **PRIOR-ART-KILL** | **Vulture's shipped whitelist, verified in-repo** — the loop had already killed N10 for exactly this in run 7 and then re-derived it |
| 5 | Interface cost: arbitrary = `ν(M)` bits, allowlist = 5.13 bits more | **INCREMENTAL** | Wolpert 1996 (NFLT); `6.129283` NO SOURCE FOUND as a prior published value |
| 6 | 21/21 real-repo certificates are class-level, not per-symbol | **INCREMENTAL** | the 21/21 measurement is new data; the structural claim is the standard open-world limit (cf. Ray et al., FSE 2017) |
| 7 | Run 7's 0.875 is predicted by the law | **INCREMENTAL** | arithmetic verification of claim 3 |

**Three most damaging citations.**
1. **Reiter, R. (1978), "On Closed World Data Bases"** — the formalisation behind the exact binary the loop presented as a finding. Verified via the Wikipedia CWA entry; the primary source was not reached.
2. **`jendrikseipp/vulture`, README, "Whitelists"** — ships the per-symbol allowlist the claim calls irreducible. Verified in-repo. This is the *second* time this loop rediscovered Vulture's mechanism (run 7 killed N10 on it) and then re-derived it as a discovery.
3. **Salis et al., PyCG, arXiv:2103.00587** — the Python CPG baseline this loop never cited until run 6; 99.2% precision / 69.9% recall with dynamic calls left unresolved, i.e. the open-world limit is already accepted in the literature.

**Could NOT be verified — recorded, not papered over.**
- Cook & Goodwin (ECOOP 1999) URL: DBLP and Google Scholar returned 403/429. Citation form confirmed via Netzer 2011's reference list. **UNVERIFIED-URL, VERIFIED-CITATION.**
- Ray et al., FSE 2017 (Sourcerer), DOI 10.1145/3243734.3243803: ACM DL 403. **UNVERIFIED-URL, VERIFIED-CITATION.**
- Any published information-theoretic lower bound of the form *"N bits of interface declaration are required to analyse P"*: **NO SOURCE FOUND** after arXiv and web attempts. Not fabricated.
- Any prior publication of the **19683-gate enumeration** or the **6.129283-bit** value: **NO SOURCE FOUND.** These are this loop's measurements, not prior results.

**The finding that the check produced, and it was not a novelty result at all.** The math
verification was asked to refute the law and asked *what is a bit, and is the achiever sound?*
The second question is the one no assertion in nine runs had asked: the enumeration maximised
**agreement** over an **unconstrained** gate family, so its reported maximum was attained by the
gate that certifies live symbols. Five self-checks missed it because the agreement and sound
curves coincide at `j = 0`. The loop's own self-checks assert that the docstring's claims hold;
they never assert that the *quantity being maximised* is the quantity the deliverable needs.
Retraction and both repaired curves: `equations.md` row 30.


---

# Run 10 / N12 — prior-art and novelty check

**Target.** The corrected law `acc*(Pi) = 1 - |D ∩ mixed(Pi)| / |S|` (row 33), the
retraction of N11c's flat law (row 32), and the negative carrier result.

**Method, stated first because it is part of the finding.** Two of the three
dispatched research sub-agents died on provider quota (Gemini free tier
`429 RESOURCE_EXHAUSTED`, and a second provider's daily free-model cap). A third
returned a report written to its own sandbox that never reached this workspace, and
a request to re-emit it inline came back empty. The searches below were therefore run
directly. **No citation below was produced by a sub-agent**, and every claim that
could not be verified by a direct search is marked UNVERIFIED. Two providers failing
is also why this check is thinner than runs 6 and 7's, and the novelty score is
marked provisional for that reason.

## Verified prior art

| # | Sub-claim | Prior art | Verdict |
|---|---|---|---|
| 1 | A classifier constrained to be constant on a partition is optimal by the majority rule per block | **CART** — Breiman, Friedman, Olshen & Stone, *Classification and Regression Trees*, Wadsworth, 1984, DOI `10.1201/9781315139470`. Ch. 3 "Tree Classification", ch. 9 "Bayes Rules and Partitions". The recursive-partitioning literature states the primitive outright: "each split in the tree building process results in daughter nodes that are more 'pure' than the parent node… Pure nodes containing only observations of one class receive an impurity value of zero, while mixed nodes receive higher impurity values" | **PRIOR_ART_STANDARD.** This is the identity, in the language it was invented in. Row 33's law is CART's per-leaf majority rule read under a one-sided (precision-1) constraint, and the loop must not claim it |
| 2 | The `1 - errors/|S|` shape and the pure/mixed primitive | Same as #1. Impurity **is** the mixed-node fraction, so `acc* = 1 - impurity` is the same identity restated | **PRIOR_ART_STANDARD** |
| 3 | The trivial information-theoretic floor `log2 C(n, k)` for labelling a class of `n` with `k` dead members | Information theory; not searched separately because row 31's use of it was already standard and is not what this run claims | **PRIOR_ART_STANDARD** |
| 4 | A partial annotation buys a sound analysis **some** precision, and the amount is worth quantifying | **Aiken, "Soundness and its Role in Bug Detection Systems"** (Stanford, 2005) states the adjacent fact — "it is usually impossible to compute both a sound and reasonably precise… analysis", "most sound systems will assume at least some user annotations" — but does **not** quantify what a partial annotation buys | **NOVEL-but-taxonomic.** The nearest published neighbour stops one step short of the quantity |

## Not found, and therefore claimed as unoccupied rather than as novel

| # | Sub-claim | Search performed | Result |
|---|---|---|---|
| 5 | "A declaration is worth nothing unless it makes every equivalence class pure" | `label complexity of class-conditional prediction`, `version space`, `partial label`, `teaching dimension`, `hypothesis class`, `refinement of a partition`, `identifiability` | **Not found.** Partial-label learning is a mature field (Cour et al., JMLR 2011; Zhang et al., NeurIPS 2020 "Provably Consistent Partial-Label Learning"; Alon, Hanneke, Holzman & Moran, FOCS 2021 on partial concept classes) but it counts *labels*, not *purities*. Nothing states the purity-value identity |
| 6 | The same statement in the program-analysis literature | `static analysis annotation cost`, `price of precision`, `how many annotations does an analyzer need`, `precision of the abstraction lattice` | **Not found.** The precision literature (Klinger, Christakis & Wüstholz, arXiv:1812.05033; Regehr et al., TOPLAS/OOPSLA "Testing Static Analyses for Precision and Soundness"; Møller et al. on TAJS) measures precision as *imprecision to remove*, never as *value of a partial declaration* |
| 7 | Any dead-code tool using a carrier other than a bare-name allowlist, underscore convention, exclusion globs, or per-class/per-module scoping | Loop's own run-7 finding stands and was not re-run: Vulture's `whitelist` + `vulture/whitelists/` | **PRIOR_ART_STANDARD for the allowlist** (run 7, verified in Vulture's own `core.py`). **UNVERIFIED** for the wider tool survey — `deadcode`, `pyflakes`, `unimport`, `knip`, `cargo-machete`, Rust `dead_code`, `noUnusedLocals` were **not** re-examined this run |
| 8 | Type-inference-derived deadness for a whole class at once (Pyre / mypy / Pyright) | — | **UNVERIFIED.** Not searched this run |
| 9 | Sound whole-program points-to / devirtualization for Python (PyCG, Pythia, eta, Scalpel) | — | **UNVERIFIED.** Run 6 already recorded PyCG (arXiv:2103.00587, MSR 2021) as the real Python CPG baseline; nothing this run bears on it |
| 10 | Abstract interpretation of reflection strings (REFS) as "declare the strings and the property becomes decidable" | — | **UNVERIFIED.** Run 7 already queried the closed-world-assumption line (Reiter 1978) and Cook & Goodwin 1999 |
| 11 | The negative result: no corpus-derived partition (class / file / module / package / arity / decorated) isolates any dead method in a protocol class | — | **Not found**, but this is the run's own measurement on its own fixture. No prior-art search can be expected to cover it, and it is a fact about `synthetic_index_repo` |

## Scores

- **Corrected law (row 33): 38/100.** The mathematics is CART and scores `PRIOR_ART_STANDARD`; the *dead-code certification* application, the precision-1 residual statistic `|D ∩ mixed|` as the steering quantity, and the carrier enumeration are not published. Engineering track, **no LaTeX paper** — a paper whose theorem is Breiman et al. 1984 chapter 3 will not survive review, and the loop says so rather than reframing it.
- **The retraction itself (row 32): 55/100.** The specific claim is unoccupied (#5), but a retraction is not a research contribution and is not scored as one. What is defensible is the **transferable methodological finding**, and that is the one thing in this run worth carrying forward: *a law computed inside a chosen hypothesis class was published as a property of the problem, in two consecutive runs, by two different mechanisms.* That is a real and repeatable failure mode of automated research loops, and no published work on that was found.
- **Provisional.** Three of ten sub-claims are UNVERIFIED because two providers rate-limited and one sub-agent's output was lost. Re-run this check when quota returns; a sub-100 score here should be expected to fall, not rise, as #7–#10 get checked.

## What the loop claims, in one line

The loop claims **no new mathematics**. It claims one correction, one measured negative, one empty instrument channel, and one methodology note. Novelty **15 → 38/100** is an *increase* on run 9's 15, and it is reported as such rather than as progress: the increase is entirely the retraction's worth, which is not novelty.
