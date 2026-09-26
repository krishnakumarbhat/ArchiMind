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
