DENSE ADVERSARIAL REVIEW — N10 / RUN 7 EXPERIMENT PLAN (read-only)

(a) FIDELITY — sentinel-return is a LOWER BOUND, truth INCOMPLETE, precision OPTIMISTIC.
  • Your driver executes `getattr(obj, name)` over a user-chosen tuple (protocol names).
    Any real framework (SQLAlchemy, stdlib logging, rich) may dispatch additional names
    (e.g. `bind_processor`, `flush`, `close`, a user-defined subtype method) that
    your tuple omits. A method your driver misses may STILL be reachable → your
    "executed" set ⊂ true reachable set. Precision computed against this is OVERSTATED.
  • It is NOT a trace: it does not observe intermediate calls (`getattr` called by
    framework code is unseen; only the direct call against your instance is measured).
    It proves "this name reaches this object", not "no other path reaches it".
  • To make sound: declare a CLOSED protocol list P (SQLAlchemy TypeEngine docs:
    process_bind_param, process_result_value, coerce_compared_value, bind_processor,
    result_processor; stdlib Handler: emit, flush, close; rich: emit + flush + close).
    Driver enumerates ALL p ∈ P. Argument: any framework driver uses the same doc
    protocol; no name outside P can reach the method by name-based dispatch. Assert
    the list in code (`assert P == {...}`) and emit `manifest_coverage` = |P_executed|/|P|.
  • Code-level: add `PROTOCOL_NAMES = frozenset([...])` at top of fixture module;
    compute `truth_executed = {name for name in PROTOCOL_NAMES if getattr(obj,name)()
    returns sentinel}`; include `truth_incomplete = PROTOCOL_NAMES - truth_executed`.

(b) CIRCULARITY — derive truth from INSTALLED libraries, not user-constructed fixture.
  • Fixture symbol names (`process_bind_param`, etc.) are user-constructed. Even if
    sourced from SQLAlchemy docs, the DEAD-collision method (`dead_collides_by_name`)
    and private dead functions are hand-written, so a rule tuned to them proves nothing.
  • Independent source: sqlalchemy (installed) and rich (installed) both contain REAL
    protocol-method definitions (`sqlalchemy.types.DateTime` subclasses, `rich.logging`)
    and REAL private dead code (unreferenced internal helpers). sqlmodel is NOT
    installed — use the installed sqlalchemy directly for truth construction.
  • Strongest design (proposed):
    1. Extract the REAL class `sqlalchemy.types.DateTime` source from installed
       package (`import sqlalchemy.types; inspect.getsourcefile`); build fixture
       from that file (not rewritten class T).
    2. Use actual installed `rich.logging.RichHandler` for `emit` truth.
    3. The dead-collision method must be a REAL name taken from an installed package
       that is NOT in any installed package's protocol interface (e.g. scan all
       installed `.py` for a method name that appears only in private helpers, not
       in any public API; verify via `import pkg; [m for m in dir(...) if ...]`).
    4. The non-protocol dead method: scan installed package for a method whose name
       does NOT match any entry in PROTOCOL_NAMES and has occ == 1 in the fixture.
    5. Report `fixture_source = "installed_sqlalchemy_rich"` in JSON to prove
       independence from user construction.

(c) R10b (environment-augmented corpus) — FOREGONE CONCLUSION (~0 rate), but NOT WORTHLESS.
  • Yes: site-packages = 224MB, >4000 .py files easily. `occ[name]` for any common
    protocol name (`emit`, `load`, even `bind`) will be >>1. Certification rate → ~0.
    Measuring R10b as a CERTIFICATION RULE wastes the iteration.
  • To make it NOT foregone: measure R10b as COLLISION-EXPOSURE, not certification.
    Stream-tokenise installed packages and count, per fixture symbol name, how many
    installed packages mention it. Output field: `collision_exposure[name] = int`.
    This yields a real number (fraction of fixture dead names that collide with
    installed packages) and explains WHY the fixture must use immune names (see e).
  • Also: compute `environment_blocked_by_install = {name: count}` for R5/R10a
    when run with site-packages added; this shows the over-blocking cost quantitatively.

(d) TRUNCATION PRECONDITION — `corpus_complete` (eq 20) is UNSATISFIABLE for environment corpus.
  • `MAX_CORPUS_FILES = 4000`, `MAX_FILE_BYTES = 200_000`. Python site-packages
    exceeds 4000 files (many small .py files in metadata, tests, subpackages). Any
    file >200KB (compiled .pyc is skipped; some large generated modules may exceed)
    is dropped silently. `corpus_complete` requires `n_tokenised == n_py_in_artefact`
    → false when any file is dropped. So R10b must refuse to score on every machine.
    It is vacuous as a certification rule.
  • Cheapest sound alternative: TARGETED import-reachable scan, NOT full site-packages.
    Design:
    1. Compute import graph from analysis set (fixture files): collect all modules
       reachable via `import X` or `from X import ...` (static + runtime `sys.modules`
       after loading fixture).
    2. Resolve each module to its installed `.py` path (`importlib.util.find_spec`).
    3. Stream-tokenise ONLY those files (no 4000 cap; cap = number of reachable files,
       which is bounded by the import graph, typically <200). Skip-on-parse-error
       is counted as `<unparsed>` and makes `corpus_complete` false (correct refusal).
    4. Do NOT include unreachable installed packages — a package not imported by the
       corpus cannot statically reference a symbol in the corpus (dynamic import is
       the undecidable ceiling already named).
  • Recommend TARGETED over STREAMING-FULL: targeted satisfies `corpus_complete`
    with a small bounded set, avoids RAM explosion (224MB token stream pushes peak
    near 380MB with dict overhead), and is sound relative to static import. Streaming-
    full is sound only if you count `<unparsed>` holes; but it will always refuse
    (some installed file always fails parse, is skipped by size cap, or exceeds cap).
    Code: `import importlib.util; spec = importlib.util.find_spec(mod_name); src_path = spec.origin`.

(e) LEAKAGE — site-packages WILL block fixture protocol names. Name collision risks:
  • HIGH: `emit` → stdlib logging.Handler.emit; `load` → json.load, yaml.load,
    package loaders, SQLAlchemy loaders, pytest fixtures; `close` → common.
  • MEDIUM: `process_bind_param` / `process_result_value` / `coerce_compared_value`
    → installed sqlalchemy.types (they exist; blocking them is expected for the
    EXTERNAL-DRIVER case, but site-packages also blocks them, making the fixture
    measure ambiguous).
  • The DEAD-collision method: if named `process_result_value` (colliding with
    protocol), the manifest should block it; but site-packages also blocks it via
    occurrence >1, making it impossible to tell whether the manifest or the collision
    did the work.
  • Immune naming strategy:
    1. Protocol names: must be REAL protocol names (they are the point), but report
       `installed_occurrence[protocol_name]` separately so leakage is visible.
    2. Dead-collision method: choose a name guaranteed absent from installed packages.
       Scan site-packages first (`grep` over all `.py` for candidate name); pick a
       gibberish prefix (`fixture_dead_collision_` + random hex) and assert
       `installed_occurrence[name] == 0` in fixture setup.
    3. Non-protocol dead method: same immune naming (`fixture_nonprotocol_dead_...`).
  • Reporting around leakage: for each symbol in fixture truth set, emit:
    `"collision_risk": {"installed_mentions": int, "installed_modules": [str]}`.
    For R5/R10a results, emit `"blocked_by_environment"` as a subset of withheld,
    so any certificate attributed to sound withholding is not conflated with
    over-blocking. Without this field, a zero-certification result for R10b looks
    like "perfect precision" when it is actually "total leakage".

(f) MOST LIKELY CONFLATED / OVERSTATED RESULT — aggregate metric hides R10b over-blocking.
  • The experiment compares R5 / R10a / R10b paired on same fixture. R10b will withhold
    EVERY protocol-method symbol (installed sqlalchemy/rich mention them) AND the
    dead-collision method (if named poorly) AND possibly the non-protocol method (if
    common name). Its `certified_set` will be empty or near-empty. Reporting a single
    aggregate `precision` or `harness_score` without disaggregating WHY each symbol
    was withheld makes R10b look like a "better, more conservative" rule, when it is
    actually an over-blocked one.
  • The false claim it enables: "R10b improves soundness by reducing false positives"
    — false, because there are zero false positives ONLY because recall is zero.
  • Exact field in output JSON to expose it: include `"withheld_reasons"` mapping each
    symbol → reason string (`manifest_block`, `installed_collision`, `name_occurrence`,
    `external_driver`), and `"per_symbol_adjudication"` listing, for each ground-truth
    dead/live symbol, which rules certified / withheld it and which reason applied.
    Without this field, `"certified_set"` alone conflates sound withholding with
    leakage. Another exposing field: `"collision_exposure"` (see c/e) per symbol.
  • Also: emit `"manifest_coverage"` = fraction of executed protocol names actually
    listed in manifest. If <1.0, any claim "manifest closes hole" is overstated.

(g) MOST LIKELY FALSE CLAIM THIS RUN WILL RETRACT — "The protocol manifest eliminates
  the out-of-corpus driver residual completely."
  • Why false:
    1. Manifest is hand-maintained and open-ended. New SQLAlchemy releases add methods;
       new user subtypes define new protocol names. The manifest is always partial.
       Claiming "eliminates" implies closure; it is an approximation.
    2. The executed truth is a lower bound (see a). A method your driver does not reach
       (e.g., a user-defined subtype method called by framework reflection) may still
       be reachable. So withholding by manifest is sound only for the CLOSED list P,
       not for the world.
    3. Site-packages leakage (see c/e) means the fixture measurement conflates
       manifest withholding with environment blocking. The 4 real-repo residuals
       (flask, requests, sqlmodel, rich) may include additional protocol names not
       in the manifest (e.g., SQLAlchemy's `bind_processor`, stdlib `flush`). The
       experiment may report "4 residuals withheld" without verifying the manifest
       actually covered all 4; some may have been blocked by environment collision
       rather than manifest.
  • Prior pattern: run-4 claimed "zero false positives" unconditionally; run-5's
    gate was unsound; N9's H3 had wrong sign; N9's H2 was unsound. The recurrent
    sin is stating a soundness CLAIM unconditionally rather than conditionally.
    The retraction for this run will likely state: "The manifest withholds ONLY the
    named protocol names; it does not close the runtime-assembly ceiling (computed
    names, reflection, user subtype dispatch). The residual is reduced, not eliminated."
  • Defensive code recommendation: emit `"manifest_is_approximation": true` and
    `"soundness_claim": "withholds named protocol names only; does not cover computed-key dispatch or unlisted framework extensions"` in the output JSON. Assert this string
    in code so the claim is auditable.

SKIPPED / ADD-WHEN (ponytail):
  • Not building full site-packages stream scanner; add only targeted import-reach scan.
  • Not using sys.settrace; add when full framework-level trace against installed SQLAlchemy
    is needed to close truth beyond protocol list P.
  • Not removing fixture dead-collision from truth; replace with installed-source-derived
    truth when available.
  • Add to output JSON: `withheld_reasons`, `collision_exposure`, `manifest_coverage`,
    `truth_incomplete`, `installed_occurrence`. Assert dead-collision name has
    `installed_occurrence == 0` in fixture setup.
