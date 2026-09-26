"""Export-boundary dead-code gate: N9, and the two things it got wrong.

Purpose: run 5 (``src/04_symbol_domain.py``) certifies a predicted-dead symbol
    ``s`` when ``occ[leaf(s)] == 1`` over the whole tokenised corpus -- the one
    occurrence being ``s``'s own ``def`` -- and calls the rule *structurally
    immune*, because "every mechanism that can put a reference to ``s`` into a
    Python program names ``s`` somewhere in the source". It certifies only
    2-20% of the predicted-dead set on real repositories, and the consumer-
    boundary node (N9) exists to explain and fix that conservatism. N9 proposed
    three things. **All three were tested. Two are refuted, one survives as a
    taxonomy, and the refutations are the finding.**

    HYPOTHESIS H1 (N9's headline) -- REFUTED BY THIS MODULE'S OWN SELF-CHECK.
    ``from m import *`` copies every public top-level name of ``m`` into the
    importing module WITHOUT spelling those names: the importing source spells
    ``m`` and ``*``. So run 5's immunity claim looked false on inspection --
    a live symbol whose name is never mentioned would be certified. It is not,
    and the reason is one step further: a star import creates a BINDING, and
    every way of *dispatching* through a binding requires naming it. To call
    ``n()`` the consumer writes ``n``; to call ``m.n()`` it writes ``n``. The
    only nameless route is reflection (``vars(m)``, ``dir(m)``, ``getattr`` over
    a computed key), which is the runtime-assembly ceiling run 5 already named.
    :func:`self_check` is the adversarial test of exactly this: a consumer that
    star-imports and calls, and a consumer that star-imports and never calls.

    WHAT SURVIVES OF H1 IS A PROOF DEFECT, NOT A RULE DEFECT. Run 5's
    soundness argument enumerates the mechanisms that can create a reference to
    a module-level name -- import, assignment, attribute store, container store,
    ``globals``/``getattr`` -- and the star import is not on the list. The
    conclusion is right; the enumeration is incomplete, and closing it needs one
    extra lemma, stated as :func:`name_to_dispatch_lemma` and asserted below.
    The residual is reflection, which was already declared undecidable.

    H2 (N9's fix for the conservatism) -- REFUTED, AND IT IS UNSOUND.
    Scope the occurrence count to the defining module, so a same-basename
    collision in another package stops blocking a dead symbol. It raises the
    certified count and it is wrong: a cross-module caller writes the leaf name
    in the CALLER's file (``import m; m.n()``), so the defining module still
    holds exactly one occurrence -- its ``def`` -- and the rule certifies a
    demonstrably live symbol. :func:`certify_per_module` ships, measured and
    labelled UNSOUND, so the refutation is reproducible instead of asserted.
    The global count is kept: eq. row 16 already recorded that this rule buys
    precision, not recall.

    H3 (N9's ``__all__`` reclassification) -- REFUTED IN ITS STATED DIRECTION.
    N9 predicted that treating ``__all__`` entries as liveness witnesses would
    RAISE the certified count. It cannot, and this is structural rather than
    empirical: a symbol with an export witness is exactly a symbol that must
    NOT be certified, so moving it out of the candidate set can only shrink
    ``certified_dead``. N9's premise about the SIGN of the effect is wrong.

    THE REPLACEMENT CLAIM, AND IT IS THE ONE THAT SURVIVES. The conservatism
    is not a tuning defect and there is no cheaper sound rule. Let ``R(m)`` be
    any over-approximation of the set of modules that can hold a binding to
    module ``m``. A dispatch to ``m.n`` from module ``P`` requires BOTH that
    ``P`` spells ``n`` AND that ``P in R(m)``; so

        certified = { s = m.n in dead : no P in R(m) spells n }

    and the rule is sound for every sound ``R``. :func:`certify_dead_within_corpus`
    takes ``R(m) = all modules``, which is the IDENTITY over-approximation and
    the cheapest one available. Every cheaper ``R`` -- import-graph reachability,
    intra-package scoping -- is an aliasing- and ``__import__``-bound static
    analysis problem, i.e. the entire subject of static analysis, and an
    under-approximated ``R`` converts run 5's sound rule into an unsound one
    (that is H2, measured). The measured 2-20% certification rate is therefore
    the PRICE OF SOUNDNESS, stated as a theorem, not a defect awaiting a fix.

    WHAT IS SHIPPED, because it is the half of N9 that was right. Run 5 emits
    one verdict, "unreferenced within this corpus at this revision", and the
    loop has been reading it as "dead". Those are different claims, and the
    conservative rule is unreadable without knowing what the other 80-98% is.
    :func:`classify_dead` partitions the predicted-dead set three ways and
    :func:`attribute_blockers` says, per blocked symbol, WHICH mechanism blocked
    it. Both are trace-free, both are pure reporting, and neither can change a
    certification: the shipped :func:`certify_dead_within_corpus` is asserted
    EQUAL to run 5's rule on every repository measured, because no repository
    measured contains a star import at all.

      * ``certified_dead``     -- no reference and no export witness. Scored.
      * ``publicly_exported``  -- the module DECLARES the name in ``__all__``,
                                  or a star import can bind it. The consumer set
                                  is outside the corpus and unknowable, so the
                                  honest verdict is "not dead-verdictable", not
                                  "dead". Never certified.
      * ``blocked_by_mention`` -- the name occurs elsewhere for a reason
                                  unrelated to export, now attributed to
                                  ``dunder_all`` / ``cross_module_collision`` /
                                  ``string_literal_only`` / ``internal_reference``.

    NAMED CEILINGS, unchanged from run 5 and not solved here: a name assembled
    at runtime (``getattr(m, "_a" + "bc")``, or ``dir(m)`` feeding a dispatch
    table) is undecidable statically; and a public symbol of a library is called
    by consumers outside this repository, which is why it gets its own bucket
    rather than a dead verdict.

    ponytail: ``ast`` for structure, reuse of run 5's token counts for
    frequency. A second tokeniser would be a second thing to keep honest.
"""
from __future__ import annotations

import ast
import importlib
import os
import sys
from typing import Dict, List, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DOMAIN = importlib.import_module("src.04_symbol_domain")

Symbol = str
Module = str
Counts = Dict[str, int]

STAR = "*"
UNRESOLVED_PREFIX = "<unresolved-star:"

#: Blocked-symbol attribution, in the order a reader should care about.
BLOCKER_REASONS = (
    "dunder_all_declared",
    "cross_module_collision",
    "string_literal_only",
    "internal_reference",
    "unknown",
)

#: NAME prefixes an out-of-corpus driver collects by, with the driver named.
#:
#: This is the surviving half of N9, with the SIGN CORRECTED. N9 wanted the
#: consumer boundary to ADD certificates; it can only ever REMOVE them, and on
#: real code it removes a demonstrated false-positive class:
#:
#:   * ``test_*``  -- pytest collects test functions and methods by name. It
#:     lives outside the corpus and never spells the name, so a ``docs_src``
#:     test function occurs exactly once and run 5 certifies it as dead.
#:   * ``time_*`` / ``track_*`` -- pytest-benchmark and asv both call every
#:     such method on a collected suite class, by convention, from outside.
#:   * ``bench_*`` / ``benchmark_*`` -- the same convention, other runners.
#:
#: ``setup_`` and ``teardown_`` were in this list and were REMOVED after
#: measuring what they caught: asv spells its suite fixtures ``setup`` and
#: ``teardown`` without the underscore, so the underscore forms match nothing,
#: and on flask they withheld three real lifecycle hooks
#: (``App.teardown_appcontext``, ``Blueprint.teardown_app_request``,
#: ``Scaffold.teardown_request``). A convention list is only evidence if it is
#: checked against the convention.
#:
#: NOT adjudicated by execution: the driver was not run, so these are
#: ``externally_driven``, not measured false positives. Withholding a
#: certificate cannot create a false positive, so the clause is sound in the
#: one direction that matters and costs only recall.
EXTERNAL_DRIVER_PREFIXES = ("test_", "time_", "track_", "bench_", "benchmark_")

#: Top-level path components whose contents are driven from outside the corpus:
#: benchmark suites, documentation examples, maintenance scripts, and the
#: well-known driver files. Same one-directional power as the clause above.
EXTERNAL_DRIVER_SURFACES = ("benchmarks", "benchmark", "docs_src", "scripts",
                            "examples", "example", "nox", "conftest", "noxfile",
                            "tasks", "fabfile", "docs")


def bare(sym: Symbol) -> str:
    """Leaf name of a module-qualified symbol (``a.b.C.m`` -> ``m``)."""
    return sym.rsplit(".", 1)[-1]


def owner(sym: Symbol) -> Module:
    """Defining module of a module-qualified symbol (``a.b.C.m`` -> ``a.b.C``)."""
    return sym.rsplit(".", 1)[0] if "." in sym else ""


def name_to_dispatch_lemma() -> str:
    """The extra lemma run 5's soundness proof was missing, as one sentence.

    Kept as text and asserted in :func:`self_check` because a soundness claim
    with an unstated lemma is exactly what runs 4 and 5 each retracted.
    """
    return (
        "A star import creates a BINDING to m.n that spells n nowhere, but "
        "every way of dispatching through a binding names it: Name and "
        "attribute lookups both spell the leaf, a subscript spells it as a key "
        "or computes it, and the only nameless route is reflection over "
        "vars()/dir(), which is the already-named runtime-assembly ceiling. So "
        "occ[leaf(s)] == 1 is still a sound certificate."
    )


def _parse(src: str) -> ast.Module | None:
    """Parse a source, or ``None`` if it will not parse.

    ``None`` is treated as "export set unknown" everywhere below, and an unknown
    export set over-approximates the public surface -- the conservative
    direction, because the export bucket can only ever REMOVE symbols from
    certification, never add one.
    """
    try:
        return ast.parse(src)
    except (SyntaxError, ValueError, RecursionError):
        return None


def declared_dunder_all(src: str) -> Tuple[Set[str], bool]:
    """Names in a module-level ``__all__``, and whether the list is dynamic.

    Returns ``(names, is_dynamic)``. A dynamic ``__all__`` (``__all__ = []; ...
    __all__.append(x)``, or a computed list) yields ``is_dynamic=True`` and the
    caller's fallback -- the whole public surface -- which is what CPython binds
    on a star import anyway.
    """
    tree = _parse(src)
    if tree is None:
        return set(), True
    names: Set[str] = set()
    dynamic = False
    for node in tree.body:
        targets: List[ast.expr] = []
        value: ast.expr | None = getattr(node, "value", None)
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AugAssign):
            targets = [node.target]
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "__all__"
                and call.func.attr in {"append", "extend", "insert"}
            ):
                dynamic = True
            continue
        if not any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
            continue
        if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            for elt in value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    names.add(elt.value)
                else:
                    dynamic = True
        else:
            dynamic = True
    return names, dynamic


def _bound_targets(node: ast.AST) -> Set[str]:
    """Top-level names a statement binds in its own module."""
    out: Set[str] = set()
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        out.add(node.name)
    elif isinstance(node, ast.Assign):
        for t in node.targets:
            out |= _bound_targets(t)
    elif isinstance(node, ast.AnnAssign):
        out |= _bound_targets(node.target)
    elif isinstance(node, ast.AugAssign):
        out |= _bound_targets(node.target)
    elif isinstance(node, (ast.Import, ast.ImportFrom)):
        for alias in node.names:
            out.add(alias.asname or alias.name.split(".")[0])
    return out


def _bound_top_level(tree: ast.Module) -> Set[str]:
    out: Set[str] = set()
    for node in tree.body:
        out |= _bound_targets(node)
    return out


def public_surface(src: str) -> Set[str]:
    """Names ``from <this module> import *`` binds, per CPython semantics.

    With a literal ``__all__`` the star import binds exactly those names --
    including underscore-prefixed ones. Without one it binds every public
    top-level binding, i.e. every name not starting with ``_``. A dynamic
    ``__all__`` is over-approximated by the public surface, which is the set
    CPython falls back to anyway.
    """
    declared, dynamic = declared_dunder_all(src)
    if declared and not dynamic:
        return set(declared)
    tree = _parse(src)
    if tree is None:
        return set()
    return {n for n in _bound_top_level(tree) if not n.startswith("_")}


def _resolve_relative(current: Module, level: int, module: str | None) -> Module:
    """Dotted target of ``from <dots>module import *`` seen inside ``current``."""
    pkg = current.split(".")[:-1]
    if level > 1:
        pkg = pkg[: len(pkg) - (level - 1)]
    tail = module.split(".") if module else []
    return ".".join([*pkg, *tail])


def star_import_witnesses(corpus: Dict[str, str]) -> Dict[Module, Set[str]]:
    """Per module, the public names a ``from m import *`` anywhere binds.

    QUALIFIED, not bare. A star import binds ``m.n`` into the consumer under
    the local name ``n``; it never makes some *other* module's ``n`` reachable.
    So the witness is attached to ``m``, and a same-named symbol in a different
    module is untouched -- a bare filter would taint it, which is the collision
    direction eq. row 16 already recorded as a recall loss.
    """
    by_leaf: Dict[str, List[Module]] = {}
    for mod in corpus:
        by_leaf.setdefault(mod.rsplit(".", 1)[-1], []).append(mod)
    out: Dict[Module, Set[str]] = {}
    for mod, src in corpus.items():
        tree = _parse(src)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if not any(a.name == STAR for a in node.names):
                continue
            if node.module is None and node.level == 0:
                continue  # `from . import *` on a package: nothing to resolve
            target = _resolve_relative(mod, node.level, node.module)
            if target not in corpus:
                # Accept a unique basename match; an ambiguous or absent one is
                # reported as unresolved rather than guessed.
                cands = [
                    c for c in by_leaf.get(target.rsplit(".", 1)[-1], []) if c != mod
                ]
                if len(cands) == 1:
                    target = cands[0]
                else:
                    out.setdefault(UNRESOLVED_PREFIX + target, set()).add(STAR)
                    continue
            out.setdefault(target, set()).update(public_surface(corpus[target]))
    return out


def count_star_import_sites(corpus: Dict[str, str]) -> int:
    """How many ``from m import *`` statements the corpus actually contains.

    Separate from :func:`star_import_witnesses`, which counts TARGET MODULES.
    One consumer may star-import three modules, and the two numbers answer
    different questions: "is this mechanism present at all" versus "how much
    surface does it expose".
    """
    n = 0
    for src in corpus.values():
        tree = _parse(src)
        if tree is None:
            continue
        n += sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and any(a.name == STAR for a in node.names)
        )
    return n


def exported_names(corpus: Dict[str, str]) -> Dict[Module, Set[str]]:
    """Per module, every name it PROMISES to a consumer: ``__all__`` plus stars.

    A ``__all__`` entry is an explicit declaration of an outside consumer. It is
    a different kind of evidence from an occurrence: nothing in the corpus calls
    the name, and that is expected rather than suspicious.
    """
    out: Dict[Module, Set[str]] = {}
    for mod, src in corpus.items():
        declared, dynamic = declared_dunder_all(src)
        if dynamic or declared:
            out[mod] = set(declared) | (public_surface(src) if dynamic else set())
    for mod, names in star_import_witnesses(corpus).items():
        if not mod.startswith(UNRESOLVED_PREFIX):
            out.setdefault(mod, set()).update(names)
    return out


def externally_driven(dead: Set[Symbol]) -> Set[Symbol]:
    """Predicted-dead symbols an OUT-OF-CORPUS driver collects by name or path.

    The mechanism is the same shape as the star-import closure and for the same
    reason: the driver lives outside the corpus, so it never spells the symbol,
    so the occurrence count cannot see it. Withholding is the only sound
    response -- certifying is exactly the claim run 5's proof cannot support
    across a corpus boundary.

    Split out from :func:`certify_dead_within_corpus` so the caller can report
    how much of the withheld set is name-driven and how much path-driven, which
    are different strengths of evidence: a name prefix is a published driver
    convention, a path prefix is a layout habit.
    """
    by_name = {s for s in dead if bare(s).startswith(EXTERNAL_DRIVER_PREFIXES)}
    by_path = {
        s
        for s in dead
        if owner(s).split(".")[0] in EXTERNAL_DRIVER_SURFACES
        or owner(s).rsplit(".", 1)[-1] in EXTERNAL_DRIVER_SURFACES
    }
    return by_name | by_path


def external_driver_reason(dead: Set[Symbol]) -> Dict[Symbol, str]:
    """Which half of :func:`externally_driven` caught each symbol."""
    out: Dict[Symbol, str] = {}
    for s in externally_driven(dead):
        name_hit = bare(s).startswith(EXTERNAL_DRIVER_PREFIXES)
        out[s] = "name_convention" if name_hit else "path_surface"
    return out


def star_exposed(dead: Set[Symbol], witnesses: Dict[Module, Set[str]]) -> Set[Symbol]:
    """Predicted-dead symbols a star import can bind in a consumer."""
    return {s for s in dead if bare(s) in witnesses.get(owner(s), set())}


def publicly_exported(dead: Set[Symbol], exports: Dict[Module, Set[str]]) -> Set[Symbol]:
    """Predicted-dead symbols the module itself declares as public surface."""
    return {s for s in dead if bare(s) in exports.get(owner(s), set())}


def certify_dead_within_corpus(
    dead: Set[Symbol], counts: Counts, witnesses: Dict[Module, Set[str]]
) -> Set[Symbol]:
    """Run 5's rule with the star-import hole closed.

    ``certified = {s in dead : occ[leaf(s)] == 1 and not withheld}`` where
    ``withheld`` is :func:`star_exposed` (run 5's missing lemma) plus
    :func:`externally_driven` (N9's surviving mechanism, sign-corrected).

    The star clause is a NO-OP on all nine repositories measured -- no real
    Python repository in the set contains a star import. The external-driver
    clause is not a no-op: it withholds 26 of rich's 27 certificates and 19 of
    sqlmodel's 22. Withholding cannot create a false positive, so both clauses
    are sound in the only direction that matters, and both cost only recall.
    """
    exposed = star_exposed(dead, witnesses) | externally_driven(dead)
    return {s for s in dead if counts.get(bare(s), 0) == 1 and s not in exposed}


def module_name_counts(corpus: Dict[str, str]) -> Dict[Module, Counts]:
    """Per-module identifier counts -- the FALSIFIED H2 variant's input.

    Kept so the refutation is reproducible rather than asserted.
    """
    return {mod: DOMAIN.token_name_counts([src]) for mod, src in corpus.items()}


def certify_per_module(dead: Set[Symbol], per_module: Dict[Module, Counts]) -> Set[Symbol]:
    """N9's proposed fix: count the leaf name inside the DEFINING module only.

    **UNSOUND, ON PURPOSE, DO NOT SHIP.** A cross-module caller writes the leaf
    name in the caller's own file (``import m; m.n()``), so ``m``'s file still
    holds exactly one occurrence of ``n`` -- its ``def`` -- and this rule
    certifies a symbol that is demonstrably live. Retained because the
    falsification is the evidence for keeping the global count, and because
    deleting the refuted variant is how it gets re-derived next iteration.
    """
    return {s for s in dead if per_module.get(owner(s), {}).get(bare(s), 0) == 1}


def classify_dead(
    dead: Set[Symbol], counts: Counts, corpus: Dict[str, str]
) -> Dict[str, Set[Symbol]]:
    """Four-way partition of the predicted-dead set.

    Order matters and is the conservative one: an export witness beats an
    occurrence count, because "a consumer outside the corpus may call this" is
    a stronger reason not to certify than "the name occurs twice in here".
    """
    witnesses = star_import_witnesses(corpus)
    exports = exported_names(corpus)
    exposed = star_exposed(dead, witnesses)
    declared = publicly_exported(dead, exports)
    external = externally_driven(dead)
    certified = {
        s
        for s in dead
        if counts.get(bare(s), 0) == 1
        and s not in exposed
        and s not in declared
        and s not in external
    }
    # Four buckets, not three: an externally driven symbol and an exported one
    # are both withheld, but they are withheld for different reasons and
    # merging them hides which mechanism is doing the work. Kept separate after
    # the first sweep merged them and made `publicly_exported` unreadable.
    public = (exposed | declared) - certified - external
    return {
        "certified_dead": certified,
        "publicly_exported": public,
        "externally_driven": external - certified - public,
        "blocked_by_mention": dead - certified - public - external,
    }


def attribute_blockers(
    blocked: Set[Symbol],
    corpus: Dict[str, str],
    per_module: Dict[Module, Counts],
    counts: Counts,
    ident: Counts,
    exports: Dict[Module, Set[str]],
) -> Dict[Symbol, str]:
    """Say which mechanism keeps each predicted-dead symbol from being certified.

    Call it with the WHOLE predicted-dead set, not just the blocked remainder:
    the export check in :func:`classify_dead` removes every ``__all__``-declared
    symbol from ``blocked_by_mention``, so attributing only the blocked
    remainder makes ``dunder_all_declared`` unreachable and reports a
    structurally impossible zero. That bug was live for one run and is the
    reason the reason-list is ordered by *applicability*, not by intuition.

    First applicable reason in :data:`BLOCKER_REASONS` order. This is
    reporting, not scoring: it explains a conservatism the loop has been
    carrying as a mystery since run 5, and it cannot change a certification.
    """
    out: Dict[Symbol, str] = {}
    for s in blocked:
        leaf, mod = bare(s), owner(s)
        if leaf in exports.get(mod, set()):
            out[s] = "dunder_all_declared"
            continue
        elsewhere = sum(
            c.get(leaf, 0) for m, c in per_module.items() if m != mod
        )
        if elsewhere > 0 and counts.get(leaf, 0) - elsewhere <= 1:
            out[s] = "cross_module_collision"
            continue
        if ident.get(leaf, 0) <= 1:
            out[s] = "string_literal_only"
            continue
        if elsewhere > 0:
            out[s] = "cross_module_collision"
            continue
        out[s] = "internal_reference"
    assert set(out) == set(blocked)
    assert set(out.values()) <= set(BLOCKER_REASONS)
    return out


def self_check() -> None:
    """Assert the H1 refutation, the H2 falsification, and the partition."""
    assert "spell" in name_to_dispatch_lemma()

    # ---- H1: the star-import hypothesis, and the test that killed it.
    # A consumer that star-imports AND CALLS must spell the name, so the
    # occurrence count sees it and run 5 was never blind to this route.
    calling = {
        "m": "def public_n():\n    return 1\ndef _private_n():\n    return 2\n",
        "consumer": "from m import *\ndef go():\n    return public_n()\n",
    }
    counts_calling = DOMAIN.token_name_counts(calling.values())
    assert counts_calling["public_n"] == 2, counts_calling["public_n"]
    assert DOMAIN.certify_unreferenced({"m.public_n"}, counts_calling) == set()
    # A consumer that star-imports and never calls creates a binding and no
    # dispatch, so the symbol really is dead and run 5 is right to certify it.
    # This is the case the naive reading of the hypothesis called a false
    # positive; it is not one, because nothing dispatches to it.
    silent = {
        "m": "def public_n():\n    return 1\ndef _private_n():\n    return 2\n",
        "consumer": "from m import *\n",
    }
    counts_silent = DOMAIN.token_name_counts(silent.values())
    run5_silent = DOMAIN.certify_unreferenced({"m.public_n"}, counts_silent)
    assert run5_silent == {"m.public_n"}, run5_silent
    # The star witness exists in BOTH corpora -- the binding is nameless either
    # way. Only the dispatch differs, which is the whole lemma.
    assert "public_n" in star_import_witnesses(calling).get("m", set())
    assert "public_n" in star_import_witnesses(silent).get("m", set())
    # A leading underscore is NOT bound by a star import, so the hole (had it
    # existed) would additionally have needed a public name.
    assert "_private_n" not in star_import_witnesses(calling).get("m", set())
    # An `__all__` entry names the symbol AS A STRING, so the occurrence rule
    # already counted it: the `__all__` route was never a hole either.
    dunder = {
        "dunder_all": "__all__ = ['_hidden']\ndef _hidden():\n    return 1\n",
        "consumer": "from dunder_all import *\ndef go():\n    return _hidden()\n",
    }
    counts_dunder = DOMAIN.token_name_counts(dunder.values())
    assert counts_dunder["_hidden"] == 3, counts_dunder["_hidden"]
    assert DOMAIN.certify_unreferenced({"dunder_all._hidden"}, counts_dunder) == set()
    # ...and a star import of that module binds `_hidden` via `__all__`, so the
    # qualified witness is right to name an underscore name in this one case.
    assert star_import_witnesses(dunder).get("dunder_all") == {"_hidden"}

    # ---- The closure clause is a no-op exactly where the lemma says it is.
    witnesses = star_import_witnesses(silent)
    closed = certify_dead_within_corpus({"m.public_n"}, counts_silent, witnesses)
    assert closed == set(), closed  # star-exposed -> withheld, run 5 certified it
    assert run5_silent - closed == {"m.public_n"}
    # And on a corpus with no star import the two rules are identical.
    no_star = {"a": "def twin():\n    return 1\n", "b": "def twin():\n    return 2\n"}
    ns_counts = DOMAIN.token_name_counts(no_star.values())
    ns_dead = {"a.twin", "b.twin"}
    assert certify_dead_within_corpus(
        ns_dead, ns_counts, star_import_witnesses(no_star)
    ) == DOMAIN.certify_unreferenced(ns_dead, ns_counts)

    # ---- H2: N9's own fix, measured false positive.
    corpus2 = {
        "lib.extra": "def twin():\n    return 1\ndef twin_dead():\n    return 2\n",
        "app": "from lib import extra\ndef go():\n    return extra.twin()\n",
    }
    dead2 = {"lib.extra.twin", "lib.extra.twin_dead"}
    counts2 = DOMAIN.token_name_counts(corpus2.values())
    per_mod = module_name_counts(corpus2)
    assert counts2["twin"] == 2, counts2["twin"]
    assert DOMAIN.certify_unreferenced(dead2, counts2) == {"lib.extra.twin_dead"}
    pm = certify_per_module(dead2, per_mod)
    # It certifies `lib.extra.twin`, which `app.go` calls. That is the false
    # positive, and it is the entire refutation of H2.
    assert pm == {"lib.extra.twin", "lib.extra.twin_dead"}, pm
    assert "lib.extra.twin" not in DOMAIN.certify_unreferenced(dead2, counts2)
    assert certify_dead_within_corpus(
        dead2, counts2, star_import_witnesses(corpus2)
    ) == {"lib.extra.twin_dead"}

    # ---- The partition, and the collision direction eq. row 16 called a loss.
    b = classify_dead(ns_dead, ns_counts, no_star)
    assert b["certified_dead"] == set(), b
    assert b["blocked_by_mention"] == {"a.twin", "b.twin"}, b
    per_ns = module_name_counts(no_star)
    reasons = attribute_blockers(
        b["blocked_by_mention"],
        no_star,
        per_ns,
        ns_counts,
        DOMAIN.recount_identifiers_only(no_star.values()),
        exported_names(no_star),
    )
    assert set(reasons.values()) == {"cross_module_collision"}, reasons

    # ---- N9's surviving mechanism, sign-corrected. A `time_*` method on a
    # benchmark suite is called by pytest-benchmark from OUTSIDE the corpus, so
    # its name occurs exactly once and run 5 certifies it as dead.
    bench = {
        "benchmarks.benchmarks": (
            "class PrettySuite:\n"
            "    def time_pretty(self):\n        return 1\n"
            "    def time_pretty_wide(self):\n        return 2\n"
        ),
        "pkg/__init__.py": "",
        "pkg/core.py": "def helper():\n    return 1\n",
    }
    bench.pop("pkg/__init__.py")
    bench = {"benchmarks.benchmarks": bench["benchmarks.benchmarks"],
             "pkg.core": "def helper():\n    return 1\n"}
    bench_dead = {
        "benchmarks.benchmarks.PrettySuite.time_pretty",
        "benchmarks.benchmarks.PrettySuite.time_pretty_wide",
        "pkg.core.helper",
    }
    bench_counts = DOMAIN.token_name_counts(bench.values())
    # Run 5 certifies all three -- two of them live by an external convention.
    assert DOMAIN.certify_unreferenced(bench_dead, bench_counts) == bench_dead
    drv = external_driver_reason(bench_dead)
    assert set(drv.values()) == {"name_convention"}, drv
    # A path-only case: no name convention, but a driver-owned directory.
    pathy_dead = {"scripts.docs.copy_py39", "pkg.core.helper"}
    assert set(external_driver_reason(pathy_dead).values()) == {"path_surface"}
    # The gate withholds the external ones and keeps the genuine one.
    assert certify_dead_within_corpus(
        bench_dead, bench_counts, star_import_witnesses(bench)
    ) == {"pkg.core.helper"}
    # Withholding is one-directional: it can only ever remove certificates.
    assert certify_dead_within_corpus(
        bench_dead, bench_counts, star_import_witnesses(bench)
    ) <= DOMAIN.certify_unreferenced(bench_dead, bench_counts)

    assert count_star_import_sites(calling) == 1
    assert count_star_import_sites(silent) == 1
    assert count_star_import_sites(no_star) == 0
    assert count_star_import_sites(dunder) == 1

    # An unresolved star target is reported, never guessed.
    unresolved = star_import_witnesses({"x": "from gone import *\n"})
    assert [k for k in unresolved if k.startswith(UNRESOLVED_PREFIX)] == [
        UNRESOLVED_PREFIX + "gone"
    ], unresolved
    print(
        "05_export_boundary self-check OK",
        {
            "h1_certified_when_star_imported_and_called": sorted(
                DOMAIN.certify_unreferenced({"m.public_n"}, counts_calling)
            ),
            "h1_certified_when_star_imported_but_uncalled": sorted(run5_silent),
            "h2_UNSOUND_certified": sorted(pm),
            "closure_changed_run5_by": sorted(run5_silent - closed),
        },
    )


if __name__ == "__main__":
    self_check()
