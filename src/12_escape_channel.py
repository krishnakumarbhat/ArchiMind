"""Run 12 / N14: the binding-set carrier, and the escape channel that refutes row 18.

Three objects live here, and they are deliberately kept apart because they are
three different claims that the loop kept trying to make at once.

1. :data:`N14_RETRACTED_T1` -- the limitation theorem I set out to publish,
   together with the counterexample that killed it and the trivial statement
   that survives in its place. It is executable for run 5's reason: a retraction
   that deletes its statement cannot be audited, and the next iteration
   re-derives it.

2. The escape channel. ``certify_unreferenced`` (eq. row 18) certifies a
   predicted-dead symbol ``s`` when ``occ[leaf(s)] == 1``, justified by the
   lemma that *every mechanism that can put a reference to* ``s`` *into a Python
   program names* ``s`` *somewhere in the source*. That lemma is FALSE. The
   loop already wrote the counterexample down in
   ``experiments/fixtures/synthetic_escape_repo`` on 2026-09-26 and never
   measured it; measuring it is what this run did.

3. The sound repair, which is a THIRD global veto, plus its price.

Terminology
-----------
**escape channel** -- a way for a program to reach a symbol without its leaf
ever being a NAME token or an identifier-shaped STRING token, so the occurrence
count cannot see it. Constructing the name at run time and then ``getattr``-ing
it is the one that matters for the dead-code term.

**name-construction site** -- an AST node that can produce a name at run time:
``getattr(x, <non-literal>)``, ``eval``/``exec``, ``globals()[e]`` and its
``locals``/``vars`` siblings, ``operator.attrgetter``. A *literal* second
argument is NOT a construction site, because a literal identifier is already
counted as an identifier-shaped STRING token and therefore already blocks
certification. That distinction is the whole difference between run 5's rule
being sound and being unsound, and it is one line long.
"""

from __future__ import annotations

import ast
import keyword
from typing import Any, Dict, List, Mapping, Set, Tuple

import importlib

DOMAIN = importlib.import_module("src.04_symbol_domain")
EXPORT = importlib.import_module("src.05_export_boundary")

UNPARSED = "<unparsed>"

#: The one line of AST that separates a sound occurrence rule from an unsound
#: one. ``getattr(m, "close")`` names ``close`` as a STRING, so row 18's count
#: sees it and the rule correctly refuses. ``getattr(m, "".join(["lo", "ad"]))``
#: names ``load`` NOWHERE, so the count is 1, the rule fires, and a live method
#: is certified dead. Both are ``getattr``; only the second argument differs.
CONSTRUCTION_SINKS: Tuple[str, ...] = ("getattr", "eval", "exec", "attrgetter")
SUBSCRIPT_NAME_MAPS: Tuple[str, ...] = ("globals", "locals", "vars")


def bare(sym: str) -> str:
    """Leaf name of a module-qualified symbol."""
    return DOMAIN.bare(sym)


def _is_literal_str(node: ast.AST, src: str) -> bool:
    """True for a name argument the token count ALREADY sees.

    ``getattr(m, "close")`` is safe: ``close`` is an identifier-shaped STRING
    token, so row 18's count sees it and refuses to certify. Two shapes are
    NOT safe and both were found by this module's own self-check:

    - ``getattr(m, "".join(["lo", "ad"]))`` -- the name is never spelled.
    - ``getattr(m, "lo" "ad")`` -- CPython folds adjacent string literals at
      PARSE time, so ``ast`` sees one constant, while ``tokenize`` still emits
      two STRING tokens. The AST therefore says "literal identifier" and the
      token count says "the identifier ``load`` never appears". Classifying on
      the AST alone would have vetoed nothing here and missed a real escape.
    """
    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        return False
    if not (node.value.isidentifier() and not keyword.iskeyword(node.value)):
        return False
    raw = ast.get_source_segment(src, node) or ""
    # A folded literal carries interior quote characters; a single one does not.
    return len(DOMAIN.token_name_counts([raw])) == 1 and raw.count("'") <= 2 \
        and raw.count('"') <= 2


def name_construction_sites(sources: Mapping[str, str]) -> List[Dict[str, Any]]:
    """Every AST node that can build a name the occurrence count cannot see.

    Purpose
    -------
    Enumerate the escape channels, so the certifier can withhold instead of
    certifying a live symbol.

    Inputs
    ------
    ``sources`` -- module dotted path -> source text.

    Outputs
    -------
    A list of records with ``module``, ``lineno``, ``sink`` and ``literal``
    (whether the name argument is a constant string, i.e. already counted).
    """
    sites: List[Dict[str, Any]] = []
    for mod, src in sources.items():
        try:
            tree = ast.parse(src)
        except SyntaxError:
            sites.append({"module": mod, "lineno": 0, "sink": UNPARSED,
                          "literal": False})
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(
                    fn, "id", None)
                if name in CONSTRUCTION_SINKS:
                    arg = node.args[1] if len(node.args) > 1 else None
                    sites.append({
                        "module": mod, "lineno": node.lineno, "sink": name,
                        "literal": bool(arg is not None and _is_literal_str(arg, src)),
                    })
            elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Call):
                fn = node.value.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(
                    fn, "id", None)
                if name in SUBSCRIPT_NAME_MAPS:
                    key = node.slice
                    sites.append({
                        "module": mod, "lineno": node.lineno,
                        "sink": f"{name}[...]",
                        "literal": _is_literal_str(key, src) if key is not None else False,
                    })
    return sites


def effective_sites(sites: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Construction sites that are NOT already covered by the token count.

    A literal name argument is an identifier-shaped STRING token, so row 18's
    count already blocks on it. Keeping those sites would veto the corpus for
    the one shape that is provably safe, and the loop has now been globally
    vetoed twice for exactly that kind of over-refusal.
    """
    return [s for s in sites if not s["literal"]]


def certify_escape_vetoed(
    dead: Set[str],
    counts: Mapping[str, int],
    withheld: Set[str],
    sites: List[Dict[str, Any]],
) -> Set[str]:
    """Run 7's certification with the escape channel closed by a global veto.

    Purpose
    -------
    Replace an unsound rule with a sound one at the smallest possible cost.

    Inputs
    ------
    ``dead`` -- predicted-dead symbols. ``counts`` -- token name counts.
    ``withheld`` -- run 6/7's withholding set. ``sites`` -- construction sites.

    Outputs
    -------
    The certified set. If the corpus contains even ONE effective construction
    site the result is empty, because a name built at run time can be any name
    and the count cannot bound the set it can produce.

    Soundness
    ---------
    One-directional, like every other repair in this loop: withholding cannot
    manufacture a false positive, so the veto costs recall and nothing else.
    """
    if effective_sites(sites):
        return set()
    return {s for s in dead if counts.get(bare(s), 0) == 1 and s not in withheld}


def certify_escape_per_module(
    dead: Set[str],
    counts: Mapping[str, int],
    withheld: Set[str],
    sites: List[Dict[str, Any]],
    corpus: Mapping[str, str],
) -> Set[str]:
    """Scope the escape veto to the module that contains the construction site.

    **UNSOUND, ON PURPOSE, DO NOT SHIP.** Kept for the same reason run 6 kept
    ``certify_per_module``: the refutation is the evidence for keeping the
    sound version, and deleting the refuted variant is how it gets re-derived.

    A construction site in module ``A`` can name a symbol defined in module
    ``B``; the name does not have to travel within one file. Asserted on a
    two-module counterexample in :func:`self_check`.
    """
    hot = {s["module"] for s in effective_sites(sites)}
    return {
        s for s in dead
        if counts.get(bare(s), 0) == 1
        and s not in withheld
        and not (hot and DOMAIN.__dict__ and _owner_module(s, corpus) in hot)
    }


def _owner_module(sym: str, corpus: Mapping[str, str]) -> str:
    """Longest dotted prefix of ``sym`` that is a module in ``corpus``."""
    parts = sym.split(".")
    for i in range(len(parts) - 1, 0, -1):
        cand = ".".join(parts[:i])
        if cand in corpus:
            return cand
    return parts[0]


def escape_exposure(
    certified: Set[str], sites: List[Dict[str, Any]], corpus: Mapping[str, str]
) -> Dict[str, Any]:
    """How much of a certified set sits in a corpus that can build names.

    The number is an EXPOSURE, not an accuracy: a real repository is never
    executed, so a certificate here cannot be shown to be a false positive, only
    to be reachable by a channel that has produced one elsewhere. Reporting the
    two separately is the difference between a bound and a claim.
    """
    ident = DOMAIN.recount_identifiers_only(corpus.values())
    never_spelled_as_string = {
        s for s in certified if ident.get(bare(s), 0) <= counts_of_def(s, corpus)
    }
    eff = effective_sites(sites)
    return {
        "n_certified": len(certified),
        "n_effective_construction_sites": len(eff),
        "corpus_can_build_names": bool(eff),
        "n_certified_never_spelled_as_string": len(never_spelled_as_string),
        "exposed_sample": sorted(never_spelled_as_string)[:10],
        "status": "EXPOSED" if eff and never_spelled_as_string else (
            "CLEAN" if not eff else "NO_EXPOSURE"
        ),
        "is_an_accuracy_claim": False,
    }


def counts_of_def(sym: str, corpus: Mapping[str, str]) -> int:
    """Occurrences of ``leaf(sym)`` inside its OWN defining module, minimum 1."""
    mod = _owner_module(sym, corpus)
    return max(1, DOMAIN.token_name_counts([corpus.get(mod, "")]).get(bare(sym), 0))


# --------------------------------------------------------------------------
# N14a: the theorem this run set out to publish, retracted before publication.
# --------------------------------------------------------------------------

N14_RETRACTED_T1 = (
    "RETRACTED before publication (run 12). Claim: a binding carrier "
    "Pi_bind(s) := D(leaf(s)) is CONSTANT on any evidence-fibre whose members "
    "have DISTINCT leaves, because the carrier is a function of the leaf. "
    "FALSE, and it is a non-sequitur rather than a false premise: D is a "
    "function of the leaf, the leaf VARIES across the fibre, so the carrier "
    "takes different values on it. What survives is trivial -- a leaf-keyed "
    "carrier is constant WITHIN each leaf class, so the number of distinct "
    "values is at most the number of distinct leaves -- and it is recorded "
    "because the loop's own failure mode is publishing a number measured in "
    "one chosen setting as a property of the problem (eq. rows 30, 32, 35, 37)."
)

N14_SURVIVING_T1 = (
    "For any carrier of the form c(s) = f(leaf(s)), the induced partition's "
    "number of blocks is at most the number of distinct leaves among the dead "
    "symbols, and c is constant on every subset of symbols sharing a leaf. "
    "This bounds BLOCK COUNT, not SPLITTING POWER."
)


def t1_counterexample() -> Dict[str, Any]:
    """Two symbols, one E-class, distinct leaves, split by the carrier.

    Both symbols have ``occ == 2`` -- so they share the occurrence coordinate of
    the evidence vector and sit in the same E-class -- but one's second
    occurrence is a dispatch and the other's is a string in a log line. The
    carrier separates them. This is the measurement that killed
    :data:`N14_RETRACTED_T1`, and the reason this carrier is the first
    corpus-derived one in runs 9-12 that is not constant on a distinct-leaf
    fibre.
    """
    live_src = {
        "alpha.py": "class T:\n    def beta_dispatched(self):\n        return 1\n"
                    "    def gamma_mentioned(self):\n        return 2\n",
        "use.py": "from alpha import T\nT().beta_dispatched()\n"
                  "log.info('gamma_mentioned')\n",
    }
    dead = {"alpha.T.beta_dispatched", "alpha.T.gamma_mentioned"}
    counts = DOMAIN.token_name_counts(live_src.values())
    cp = call_position(live_src)
    carrier = {s: bool(cp.get(bare(s))) for s in sorted(dead)}
    return {
        "sources": live_src,
        "occ": {s: counts.get(bare(s), 0) for s in sorted(dead)},
        "call_position": {k: sorted(v) for k, v in sorted(cp.items())},
        "carrier": carrier,
        "same_E_class": counts.get("beta_dispatched") == counts.get("gamma_mentioned"),
        "leaves_distinct": True,
        "carrier_is_constant": len(set(carrier.values())) == 1,
        "t1_refuted": len(set(carrier.values())) > 1,
    }


def binding_set(sources: Mapping[str, str]) -> Dict[str, Set[str]]:
    """Per-module set of names that module binds and can dispatch through.

    **DIAGNOSTIC ONLY. This is N14's own idea, and it cannot be the carrier.**

    Purpose of keeping it
    ---------------------
    N14 proposed exactly this set as the carrier. It cannot be one, and the
    reason is structural rather than a matter of tuning: a binding set is a
    property of the CALLER, while the certified set is a property of the CALLEE,
    so the two can only be connected by a resolver answering "does this bound
    name denote that symbol?". The identity resolver -- spelled name equals leaf
    -- collapses the carrier back into run 5's occurrence count, and every
    non-identity resolver is the alias/points-to analysis eq. row 22 already
    priced. Shipping the set as a diagnostic keeps the refutation auditable
    rather than a sentence in a log.

    The blocker that DOES work needs no resolver, because it never has to know
    WHICH symbol a call reaches: :func:`call_position` only asks whether the
    leaf is called anywhere, and it over-refuses.
    """
    out: Dict[str, Set[str]] = {}
    for mod, src in sources.items():
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        out[mod] = _bound_names(tree) & _called_leaves(tree)
    return out


def call_position(sources: Mapping[str, str]) -> Dict[str, Set[str]]:
    """Map each spelled leaf to the modules that CALL through it.

    Purpose
    -------
    Replace the token count with a relation. The only thing separating a
    blocking mention from a blocking dispatch is whether the name sits in call
    position, and the occurrence count cannot see that difference -- which is
    exactly why two symbols with equal ``occ`` can sit in one evidence fibre
    while this carrier separates them.

    Inputs
    ------
    ``sources`` -- module dotted path -> source text.

    Outputs
    -------
    leaf -> set of module names containing a call site whose callee is that
    leaf (``f()``, ``m.f()``, ``m.f.k()``). This is deliberately a
    NAME-EQUIVALENCE relation and not a points-to one: it says the spelling was
    called, never that a given binding of it reached a given symbol. That is the
    safe direction for a blocker (over-refusal) and the unsafe direction for a
    relaxation, and the two are shipped separately for that reason.
    """
    out: Dict[str, Set[str]] = {}
    for mod, src in sources.items():
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for leaf in _called_leaves(tree):
            out.setdefault(leaf, set()).add(mod)
    return out


def blocker_refined(
    dead: Set[str],
    counts: Mapping[str, int],
    cp: Mapping[str, Set[str]],
    sites: List[Dict[str, Any]],
    withheld: Set[str],
) -> Set[str]:
    """Row 18's rule with the blocker refined from "mentioned" to "called".

    SOUND as a blocker, because it only ever withholds MORE:

    - a construction site in the corpus can name anything, so any effective one
      vetoes the whole corpus (the third global veto in this loop's history);
    - otherwise an in-corpus dispatch to ``s`` is an ``ast.Call`` whose callee
      leaf is ``leaf(s)``, so ``leaf(s)`` is in call position, and it is
      withheld;
    - and a live symbol dispatched from OUTSIDE the corpus is run 6's ``R(m)``
      identity over-approximation, unchanged, plus run 6/7's withheld classes.

    What it cannot do is the other direction: certifying a symbol whose leaf is
    mentioned but never called is UNSOUND, and is shipped separately as
    :func:`relaxation_unblocking` so the refutation stays reproducible.
    """
    if effective_sites(sites):
        return set()
    return {
        s for s in dead
        if counts.get(bare(s), 0) >= 1
        and not cp.get(bare(s))
        and s not in withheld
    }


def relaxation_unblocking(
    dead: Set[str], cp: Mapping[str, Set[str]], withheld: Set[str]
) -> Set[str]:
    """Certify every predicted-dead symbol the corpus never calls. **UNSOUND.**

    This is the N14 payoff if it were sound, and it is the loop's third
    recurrence of a rule that cannot be sound: the out-of-corpus consumer is
    invisible to any corpus-wide analysis, which is run 7's impossibility result
    (eq. row 27) stated for this rule.

    Kept, labelled, and measured on every fixture with written-down or executed
    truth, because run 6's ``certify_per_module`` established that a refuted
    variant left in the tree is the evidence for keeping the sound one, and
    deleted refutations get re-derived.
    """
    return {s for s in dead if not cp.get(bare(s)) and s not in withheld}


def _bound_names(tree: ast.AST) -> Set[str]:
    """Every name this module can dispatch through: defs, classes, imports,
    parameters, assignment, loop and comprehension targets, with/except/alias."""
    out: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                out.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name != "*":
                    out.add(a.asname or a.name)
        elif isinstance(node, ast.arg):
            out.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            out.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            out.add(node.name)
    return out


def _called_leaves(tree: ast.AST) -> Set[str]:
    """Leaf names that appear in call position: ``f()``, ``m.f()``, ``m.f.k()``."""
    out: Set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name):
            out.add(fn.id)
        elif isinstance(fn, ast.Attribute):
            out.add(fn.attr)
    return out


def carrier_split_power(
    dead: Set[str], sources: Mapping[str, str], counts: Mapping[str, int]
) -> Dict[str, Any]:
    """How many evidence-fibres the binding carrier splits, on equal-``occ`` pairs.

    The measurement N14's success criterion asked for, run as written. A fibre is
    approximated by an equal-``occ`` group, which is a COARSENING of the real
    evidence vector: equal ``occ`` is necessary for membership and not
    sufficient, so any split reported here is a split of a coarser partition and
    therefore a lower bound on the carrier's power against the real fibres.
    """
    d = call_position(sources)
    groups: Dict[int, List[str]] = {}
    for s in sorted(dead):
        groups.setdefault(counts.get(bare(s), 0), []).append(s)
    split, constant = [], []
    for occ, syms in sorted(groups.items()):
        vals = {s: bool(d.get(bare(s))) for s in syms}
        (split if len(set(vals.values())) > 1 else constant).append(
            {"occ": occ, "size": len(syms), "carrier": vals})
    return {
        "n_groups": len(groups),
        "n_groups_split": len(split),
        "n_groups_constant": len(constant),
        "split_groups": split,
        "fibre_approximation": (
            "equal-occ, a coarsening of the E-vector, so these are lower bounds "
            "on the split count against true evidence fibres"
        ),
    }


def self_check() -> Dict[str, Any]:
    """Assert the retraction, its counterexample, and the escape mechanism.

    Every assertion here corresponds to a number this run publishes. Run 5's
    lesson is that a retraction which cannot be executed gets silently
    reinstated, so the retracted theorem ships as a string that a reader can
    grep for and a counterexample that makes it false on demand.
    """
    out: Dict[str, Any] = {}

    # --- N14a: the retracted theorem is false, and here is why --------------
    cx = t1_counterexample()
    out["t1_same_E_class"] = cx["same_E_class"]
    out["t1_refuted"] = cx["t1_refuted"]
    out["t1_carrier"] = cx["carrier"]
    assert cx["same_E_class"], "the counterexample must sit in one E-class"
    assert cx["t1_refuted"], (
        "N14_RETRACTED_T1 claims a distinct-leaf fibre is constant; the "
        "counterexample must make it non-constant or the retraction is wrong"
    )
    assert "RETRACTED" in N14_RETRACTED_T1
    assert "at most" in N14_SURVIVING_T1

    # --- the escape channel, on a two-module counterexample ----------------
    esc = {
        "alpha.py": "class Dyn:\n    def load(self):\n        return 7\n",
        "w7.py": "import operator\n"
                 "from alpha import Dyn\n"
                 "_D = Dyn()\n"
                 "def w7():\n"
                 "    return getattr(_D, ''.join(['lo', 'ad']))()\n",
    }
    sites = name_construction_sites(esc)
    eff = effective_sites(sites)
    out["escape_sites"] = sites
    out["escape_effective_sites"] = len(eff)
    assert eff, "the computed-name getattr must register as an effective site"

    literal = {"a.py": "def f(m):\n    return getattr(m, 'close')\n"}
    assert not effective_sites(name_construction_sites(literal)), (
        "a LITERAL name argument is an identifier-shaped STRING token, so row 18 "
        "already blocks on it; vetoing for it would over-refuse for nothing"
    )
    adjacency = {"a.py": "def f(m):\n    return getattr(m, 'lo' 'ad')\n"}
    assert effective_sites(name_construction_sites(adjacency)), (
        "adjacent string literals fold to one name at parse time, so the token "
        "count sees 'lo' and 'ad' and never 'load'; the site must be effective"
    )

    counts = DOMAIN.token_name_counts(esc.values())
    dead = {"alpha.Dyn.load"}
    assert counts.get("load") == 1, "the escape fixture is what makes occ == 1"
    assert DOMAIN.certify_unreferenced(dead, counts) == dead, (
        "the incumbent rule certifies the escaping symbol dead -- that is the "
        "refutation, so it must reproduce here"
    )
    assert certify_escape_vetoed(dead, counts, set(), sites) == set(), (
        "the veto must close the channel"
    )

    # --- the UNSOUND per-module variant, refuted ---------------------------
    cross = {
        "alpha.py": "def load():\n    return 1\n",
        "a.py": "import operator\ndef build(m):\n"
                "    return getattr(m, ''.join(['lo', 'ad']))\n",
        "b.py": "def unrelated():\n    return 2\n",
    }
    csites = name_construction_sites(cross)
    ccounts = DOMAIN.token_name_counts(cross.values())
    cdead = {"alpha.load"}
    sound = certify_escape_vetoed(cdead, ccounts, set(), csites)
    unsound = certify_escape_per_module(cdead, ccounts, set(), csites, cross)
    out["per_module_UNSOUND_certifies"] = sorted(unsound)
    assert sound == set()
    assert unsound == cdead, (
        "the construction site is in a.py and the symbol is defined in "
        "alpha.py; scoping the veto per module certifies it, so the variant is "
        "unsound and the counterexample must reproduce"
    )

    # --- oracle completeness verdict exists and is falsifiable -------------
    import importlib as _il
    oracle_mod = _il.import_module("src.01_dyn_oracle")
    empty = oracle_mod.DynOracle()
    out["completeness_empty"] = empty.completeness()["status"]
    assert empty.completeness()["status"] == "EMPTY"
    assert empty.completeness()["supports_dead_claim"] is False

    return out


if __name__ == "__main__":
    import json
    print(json.dumps(self_check(), indent=1, default=str))
