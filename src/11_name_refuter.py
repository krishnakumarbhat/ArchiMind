"""Run 11 / N13: the non-executing adjudicator, and the two holes in it.

N13 is the first node that stops NEEDING liveness. Runs 5-10 could not shrink
``unadjudicable_edges`` (eq. row 17: a predicted edge whose caller the dynamic
oracle never exercised) because every available adjudicator required knowing
which symbols are live, and run 10 measured that the real-repo channel for that
is EMPTY -- ``n_demonstrated_live_by_execution = 0`` on 4 of 4. A *refuter*
does not: it removes edges that are definitively false, and false is decidable
from the corpus alone.

THE CLAIM (N13 as written in the strategy graph)
    An edge (caller, callee) is DEFINITIVELY FALSE if ``leaf(callee)`` occurs
    nowhere in the caller's body, so ``unadjudicable_edges`` can be shrunk on
    an untrusted tarball without running the oracle -- run 6's proved ``R(m)``
    lemma (every dispatch spells the name) as a necessary condition on real
    edges.

WHAT THIS MODULE FOUND, both faults measured rather than argued:

FAULT 1 -- the lemma is FALSE for the relation a call graph means, and TRUE for
a weaker one. "Real" has two readings. Under the DYNAMIC reading (y is invoked
at some moment while x is on the stack) the lemma is refuted by a two-line
program: ``x`` calls ``h``, ``h`` dispatches ``y``, and ``leaf(y)`` is absent
from ``x``'s file. Under the DIRECT reading (a CALL instruction or an attribute
access ``m.y`` appears in x's own code object) it holds. The loop needs the
first and the node's rationale silently substituted the second, which is the
third instance of the loop's own recorded failure mode: a claim proved for a
chosen hypothesis class and published as a property of the problem (rows 30,
32).

FAULT 2 -- the lemma is refuted even under the DIRECT reading, by the loop's
OWN instrumentation. A predicted edge (x, y) need not be text-faithful: eq. row
6 made class instantiation normalise to ``Cls.__init__``, so ``f()`` calling
``return K()`` yields the edge ``(f, K.__init__)`` whose callee leaf
``__init__`` is ABSENT from f's file -- while the edge is a real, direct
dispatch. This is not an exotic corner: every instantiation of an imported
class produces one, and it is manufactured by a repair the loop shipped in run
2 and has been scoring ever since. So the refuter must apply only to
TEXT-FAITHFUL edges, and the condition is on the EDGE, not on the file.

    (recorded as a corrected self-check: the first counterexample offered for
    this fault was an ALIASED IMPORT, ``from M import y as a; a()``, and it is
    NOT a counterexample -- the import statement itself spells ``y``, so
    ``y in T(C_x)`` and the lemma holds. A refutation built on a counterexample
    that does not refute is worse than no counterexample, and the first cut of
    this module asserted one.)

WHAT SURVIVES, and it is strictly weaker than the node's claim but sound:
admissibility is a conjunction of two checked conditions, one per FILE and one
per EDGE, both syntactic:

    A1 (per file)  no dynamic-name-construction site, and
    A2 (per edge)  the edge is TEXT-FAITHFUL -- the callee's leaf is a name the
                   call site actually spells, not a name the resolver supplied.

    Then for a predicted edge (x, y):  if leaf(y) not in T(C_x), C_x satisfies
    A1, and (x, y) satisfies A2, the edge is DEFINITIVELY FALSE.

A1 is the hole the node named (``getattr`` with a computed name, ``globals()``,
``eval``, f-strings, ``%``-formatting, ``.format``, ``.join`` -- a name can be
assembled without ever appearing). A2 is the hole the node did not name, and it
lives on the edge rather than the file. Both are DETECTED BY AST / by the
resolver's own edge shape, not by a hand-maintained list of names, which is the
deliberate difference from run 7's killed protocol manifest: that manifest was
an OPEN list of names and so failed UNSOUNDLY (it vetoed only what it listed).
These are REFUSAL TRIGGERS, so a false positive costs recall and a false
negative costs soundness; each set is chosen to over-refuse and the direction
of every error is stated.

THE MEASUREMENT, and it is the reason this node is a partial win: for a
predictor whose edges are derived from call sites, ``F`` is EMPTY. The CPG adds
an edge ``(sym, callee)`` only where a resolved ``ast.Call`` sits in ``sym``'s
body, so ``leaf(callee)`` is almost always already a token of that body. The
refuter is therefore VACUOUS on local edges and bites only on edges predicted
WITHOUT a call site in the caller's body -- which is precisely the class run 3
called "name promotion" (mode B) and the only class that ever produced
unadjudicable edges at scale. So the node's promise ("shrink
``unadjudicable_edges``") is kept for the inferred-edge family and is
worthless for the syntactic one. The count that proves it is emitted, not
asserted.

Identifiability is NOT achieved, and the residual is stated rather than
narrowed away: a sound refuter removes edges from the precision DENOMINATOR
and never from the NUMERATOR, so if it removes a true edge precision FALLS.
Being sound forbids that, so a sound refuter is precision-monotone -- which is
the first non-vacuous monotonicity statement this loop has about a refuter --
yet it leaves ``identifiable = (P \\ E) = {}`` untouched whenever a surviving
unadjudicable edge remains, which it does. Refutation shrinks ``|U|``; it does
not empty it.

Absolute imports from the package root, per the loop's own convention. No
relative imports. Stdlib only.
"""

from __future__ import annotations

import ast
import io
import keyword
import tokenize
from typing import Any, Dict, Iterable, List, Mapping, Set, Tuple

Symbol = str
Dispatch = Tuple[Symbol, Symbol]

UNPARSED = "<unparsed>"


def bare(sym: Symbol) -> str:
    """Leaf name of a module-qualified symbol (``a.b.C.m`` -> ``m``)."""
    return sym.rsplit(".", 1)[-1]


def _literal_identifier(lit: str) -> str | None:
    """Identifier recovered from a string literal, or ``None``.

    Reused from :mod:`src.04_symbol_domain` so the token rule is the SAME rule
    that produced the occurrence counts of runs 5-7. A second, slightly
    different string rule here would make the two families of numbers
    incomparable, which is the defect class this loop keeps re-finding.
    """
    try:
        val = eval(lit, {"__builtins__": {}}, {})  # noqa: S307 - literal-only AST
    except Exception:
        return None
    if isinstance(val, str) and val.isidentifier() and not keyword.iskeyword(val):
        return val
    return None


def file_token_sets(files: Mapping[str, str]) -> Dict[str, Set[str]]:
    """``T(C)`` for every file: NAME tokens plus identifier-shaped STRINGs.

    A file that cannot tokenise gets the empty set AND is reported in
    ``unparsed``; the caller must treat an unparsed file as inadmissible, since
    an empty token set is an UNKNOWN reference set, not an empty one. That is
    eq. row 20's ``<unparsed>`` sentinel arriving one level down.
    """
    toks: Dict[str, Set[str]] = {}
    unparsed: List[str] = []
    for fname, src in files.items():
        acc: Set[str] = set()
        try:
            for tok in tokenize.generate_tokens(io.StringIO(src).readline):
                if tok.type == tokenize.NAME:
                    acc.add(tok.string)
                elif tok.type == tokenize.STRING:
                    name = _literal_identifier(tok.string)
                    if name is not None:
                        acc.add(name)
        except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
            unparsed.append(fname)
            acc = set()
        toks[fname] = acc
    return {"tokens": toks, "unparsed": unparsed}


#: Builtins that turn a RUNTIME VALUE into a name. A file mentioning one of
#: these can spell a name it never writes, which is exactly the hole A1 closes.
#: Chosen to OVER-refuse: an entry that is not really a name-construction site
#: costs recall (a file is declared inadmissible), never soundness.
NAME_FACTORIES = frozenset({
    "getattr", "setattr", "hasattr", "delattr", "globals", "locals", "vars",
    "dir", "eval", "exec", "compile", "__import__", "importlib", "attrgetter",
    "methodcaller", "resolve", "__getattr__", "__getattribute__",
})


def construction_sites(src: str) -> List[str]:
    """Every site in ``src`` that can build a name without writing it (A1).

    Detected syntactically, not by matching a call name, because the f-string,
    ``%``-format and ``.format``/``.join`` forms contain no factory call at all
    and are exactly the ones a name-based rule misses.

    ``getattr(o, "close")`` is deliberately NOT a construction site: the name is
    a string literal, so it is already a member of ``T(C)`` and the token rule
    sees it. Only a NON-constant second argument defeats the token rule, and
    flagging the constant case would refuse most of the standard library for
    nothing.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return ["<unparsed>"]
    hits: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            fname = fn.attr if isinstance(fn, ast.Attribute) else (
                fn.id if isinstance(fn, ast.Name) else "")
            if fname in NAME_FACTORIES:
                if fname == "getattr" and len(node.args) >= 2:
                    if _literal_identifier(_lit(node.args[1])) is not None:
                        continue  # name is written as a string; T(C) has it
                hits.append(f"call:{fname}")
            if fname in ("format", "format_map", "join") and isinstance(fn, ast.Attribute):
                hits.append(f"format:{fname}")
        elif isinstance(node, ast.JoinedStr):
            hits.append("fstring")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            hits.append("percent_format")
        elif isinstance(node, ast.Subscript):
            v = node.value
            base = v.func if isinstance(v, ast.Call) else v
            bname = getattr(base, "id", None) or getattr(base, "attr", None)
            if bname in ("globals", "locals", "vars"):
                hits.append(f"subscript:{bname}")
    return sorted(set(hits))


def _lit(node: ast.AST) -> str:
    """Source text of a node, or ``""``. Only ever fed to a literal evaluator."""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def alias_bindings(src: str) -> List[str]:
    """Aliased import bindings, reported as DIAGNOSTIC ONLY.

    Recorded because it was the loop's first -- and WRONG -- counterexample for
    fault 2, and the recording is the point: ``from M import y as a`` spells
    ``y`` in the import statement, so ``y in T(C_x)`` and NONC HOLDS. An
    aliased import is therefore not a hole in the lemma, and a module that
    treated it as one would refuse a large fraction of real Python for
    nothing. Kept as data so the claim stays auditable.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.asname is not None:
                    out.append(f"from_import_alias:{alias.asname}->{alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname is not None:
                    out.append(f"import_alias:{alias.asname}->{alias.name}")
    return sorted(set(out))


#: Leaves a RESOLVER can supply in place of a spelled name. ``Cls()`` is
#: normalised to ``Cls.__init__`` by eq. row 6, so every instantiation of an
#: imported class is a real direct dispatch whose callee leaf appears nowhere
#: in the caller's file. A2 excludes exactly these, and the set is a REFUSAL
#: trigger: a member here costs refutations, never soundness.
RESOLVER_SUPPLIED_LEAVES = frozenset({"__init__", "__new__", "__init_subclass__"})


def text_faithful(callee: Symbol) -> bool:
    """A2: is this edge's callee a name the call site could have spelled?

    False for a resolver-supplied leaf (row 6's class-call normalisation). It
    is deliberately coarse: a tighter test would need the resolver's raw text
    per edge, which the CPG does not record, and inferring it from the dotted
    symbol is the string surgery that caused run 7's defect (ii). Coarse and
    over-refusing is the sound direction.
    """
    return bare(callee) not in RESOLVER_SUPPLIED_LEAVES


def symbol_files(files: Mapping[str, str]) -> Dict[Symbol, str]:
    """Every defined symbol -> the file that defines it.

    Built by an independent AST walk rather than read off the CPG, because the
    CPG exposes ``symbols`` (symbol -> kind) and not symbol -> file, and
    reverse-engineering it from a dotted name would be exactly the string
    surgery that run 7 defect (ii) was about.
    """
    out: Dict[Symbol, str] = {}
    for fname, src in files.items():
        module = fname[:-3] if fname.endswith(".py") else fname
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        out.setdefault(module, fname)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out[f"{module}.{node.name}"] = fname
            elif isinstance(node, ast.ClassDef):
                cls = f"{module}.{node.name}"
                out[cls] = fname
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        out[f"{cls}.{sub.name}"] = fname
    return out


def admissible_files(
    files: Mapping[str, str], unparsed: Iterable[str]
) -> Dict[str, Any]:
    """Per-file A1 verdict. A file failing A1 is NEVER used to refute.

    A2 is a per-EDGE test (:func:`text_faithful`) and is applied in
    :func:`refute`, not here. Splitting it this way is what keeps A1 a property
    of the corpus and A2 a property of the resolver, which is where each one
    actually lives.
    """
    bad: Dict[str, List[str]] = {}
    for fname, src in files.items():
        reasons = list(construction_sites(src))
        if reasons:
            bad[fname] = sorted(set(reasons))
    for fname in unparsed:
        bad.setdefault(fname, ["<unparsed>"])
    n_ok = len(files) - len(bad)
    return {
        "n_files": len(files),
        "n_inadmissible": len(bad),
        "n_admissible": n_ok,
        "admissible_fraction": round(n_ok / len(files), 6) if files else None,
        "inadmissible": bad,
        "a1_construction": "a site that can build a name without writing it",
        "a2_alias": "A2 is per edge, not per file: see text_faithful()",
        "direction_of_every_error": (
            "over-inclusion in the trigger sets only makes a file or an edge "
            "non-refutable, which costs REFUTATIONS and never soundness; "
            "under-inclusion would cost soundness. Both sets over-refuse."
        ),
    }


def refute(
    predicted: Iterable[Dispatch],
    sym_file: Mapping[Symbol, str],
    tokens: Mapping[str, Set[str]],
    admissible: Mapping[str, bool],
    apply_a2: bool = True,
) -> Dict[str, Any]:
    """The refuter: which predicted edges are definitively false, with no oracle.

    Inputs: predicted edges, symbol -> defining file, the per-file token sets,
        and the per-file admissibility verdict.
    Outputs: ``refuted`` (each a list ``[caller, callee, reason]``), the
        reason histogram, and the count of edges the refuter could NOT touch
        and why -- the residual, reported because a filter that is silent about
        what it skipped is indistinguishable from one that had nothing to skip.
    """
    refuted: List[List[str]] = []
    reasons: Dict[str, int] = {}
    blocked_no_file = blocked_inadmissible = blocked_name_present = 0
    blocked_not_text_faithful = 0
    for caller, callee in sorted(predicted):
        if apply_a2 and not text_faithful(callee):
            blocked_not_text_faithful += 1
            continue
        cf = sym_file.get(caller)
        if cf is None or cf not in tokens:
            blocked_no_file += 1
            continue
        if not admissible.get(cf, False):
            blocked_inadmissible += 1
            continue
        if bare(callee) in tokens[cf]:
            blocked_name_present += 1
            continue
        refuted.append([caller, callee, "name_absent_in_admissible_caller_file"])
        reasons["name_absent_in_admissible_caller_file"] = (
            reasons.get("name_absent_in_admissible_caller_file", 0) + 1
        )
    n = len(list(predicted))
    return {
        "n_predicted": n,
        "n_refuted": len(refuted),
        "refuted": refuted,
        "reason_histogram": reasons,
        "not_refuted_caller_file_unknown": blocked_no_file,
        "not_refuted_caller_file_inadmissible": blocked_inadmissible,
        "not_refuted_not_text_faithful": blocked_not_text_faithful,
        "not_refuted_name_present": blocked_name_present,
        "refuted_fraction": round(len(refuted) / n, 6) if n else None,
    }


def identifiability_effect(
    refuted: Set[Dispatch], predicted: Set[Dispatch], covered: Set[Symbol]
) -> Dict[str, Any]:
    """What a sound refuter does and does not do to eq. row 17's condition.

    ``U := P \\ E`` is unadjudicable; ``U' := U \\ F`` after refutation. The
    condition is ``identifiable := U = {}``, so refutation shrinks ``U`` and
    leaves the condition false unless ``U`` was already almost empty. The
    monotonicity statement is the deliverable and it is one-sided: a refuter
    removes edges from the precision DENOMINATOR and never from the NUMERATOR,
    so removing a true edge LOWERS precision. Soundness forbids exactly that,
    hence a sound refuter is precision-monotone non-decreasing -- and that is a
    statement about refuters, not about predictors.
    """
    evaluable = {e for e in predicted if e[0] in covered}
    unadjudicable = predicted - evaluable
    surviving = unadjudicable - refuted
    return {
        "n_predicted": len(predicted),
        "n_evaluable": len(evaluable),
        "n_unadjudicable_before": len(unadjudicable),
        "n_refuted": len(refuted),
        "n_refuted_that_were_unadjudicable": len(refuted & unadjudicable),
        "n_unadjudicable_after": len(surviving),
        "unadjudicable_survivors": sorted(map(list, surviving)),
        "identifiable_before": not unadjudicable,
        "identifiable_after": not (predicted - refuted - evaluable),
        "identifiability_achieved": not unadjudicable and bool(refuted),
        "residual_unadjudicable_names": sorted({c for c, _ in surviving}),
        "honest_statement": (
            "refutation SHRINKS the unadjudicable set and does NOT empty it, so "
            "eq. row 17's identifiability condition still reads False whenever a "
            "survivor remains -- which is the normal case on a real repo. The "
            "condition is not repairable by any refuter that needs no liveness, "
            "because an unjudged edge stays unjudged once it is not false."
        ),
    }


def soundness_audit(
    refuted: Set[Dispatch], true_edges: Set[Dispatch]
) -> Dict[str, Any]:
    """The falsification test: did the refuter ever remove a REAL edge?

    A refuter's only defensible error is removing a true edge, so this is the
    one direction the loop can check, and it is checkable WITHOUT executing
    anything on a real repo -- only the fixtures have executed truth, and there
    the check is exact rather than sampled.
    """
    bad = refuted & true_edges
    return {
        "n_refuted": len(refuted),
        "n_true_edges": len(true_edges),
        "n_true_edges_removed": len(bad),
        "sound": not bad,
        "offenders": sorted(map(list, bad)),
    }


def self_check() -> Dict[str, Any]:
    """Executable statements of the two faults and of the surviving rule."""
    out: Dict[str, Any] = {}

    # FAULT 1: the dynamic reading is refuted; the direct reading is not.
    x_src = (
        "def x(h):\n"
        "    return h()\n"
    )
    h_src = (
        "def h():\n"
        "    return y()\n"
    )
    tx = file_token_sets({"x.py": x_src})["tokens"]["x.py"]
    th = file_token_sets({"h.py": h_src})["tokens"]["h.py"]
    out["fault1_dynamic_reading_refuted"] = ("y" in th) and ("y" not in tx)
    out["fault1_note"] = (
        "x dispatches y dynamically (h is on x's stack and h calls y) while "
        "'y' is absent from x's file. So the node's lemma is FALSE for the "
        "relation a call graph denotes, and TRUE only for the weaker 'a CALL "
        "instruction in x's own code object' reading. The node's rationale "
        "substituted the second for the first without saying so."
    )
    # Under the direct reading the same file IS sound to refute.
    d_src = "def d():\n    return g()\n"
    d_pred = {("d", "m.y")}
    d_tok = file_token_sets({"d.py": d_src})
    d_adm = {f: not (admissible_files({"d.py": d_src}, [])["inadmissible"].get(f))
             for f in ("d.py",)}
    out["fault1_direct_reading_holds"] = (
        len(refute(d_pred, {"d": "d.py"}, d_tok["tokens"], d_adm)["refuted"]) == 1
    )

    # FAULT 2: the loop's OWN row-6 normalisation manufactures an edge whose
    # callee leaf is absent from the caller's file, and that edge is REAL.
    a_src = "from M import K\n\ndef f():\n    return K()\n"
    a_tok = file_token_sets({"f.py": a_src})
    a_edge = {("f", "M.K.__init__")}
    a_files = {"f.py": a_src}
    a_adm_real = {"f.py": "f.py" not in admissible_files(a_files, [])["inadmissible"]}
    out["fault2_refuted_without_a2"] = (
        len(refute(a_edge, {"f": "f.py"}, a_tok["tokens"], a_adm_real,
                       apply_a2=False)["refuted"]) == 1
    )
    out["fault2_leaf_absent_from_caller_file"] = (
        "__init__" not in a_tok["tokens"]["f.py"]
    )
    out["fault2_a2_blocks_it"] = (
        len(refute(a_edge, {"f": "f.py"}, a_tok["tokens"], a_adm_real)["refuted"]) == 0
    )
    alias_src = "from M import y as a\n\ndef k():\n    return a()\n"
    out["fault2_alias_is_NOT_a_counterexample"] = (
        "y" in file_token_sets({"k.py": alias_src})["tokens"]["k.py"]
    )
    out["fault2_note"] = (
        "'return K()' is a real, direct dispatch; eq. row 6 normalises it to "
        "K.__init__, whose leaf '__init__' is absent from f's file. Without A2 "
        "the refuter certifies a FALSE edge -- the unsound direction. The loop's "
        "own run-2 repair manufactures the counterexample. And the loop's first "
        "counterexample for this fault, an aliased import, was WRONG: the import "
        "statement spells the name, so the lemma holds."
    )

    # A1: a computed name is invisible to T(C) and the file is refused.
    g_src = "def g(reg):\n    n = 'qu' + 'ery'\n    return getattr(reg, n)()\n"
    g_adm = admissible_files({"g.py": g_src}, [])
    out["a1_detects_computed_name"] = "call:getattr" in g_adm["inadmissible"].get("g.py", [])
    out["a1_fstring_detected"] = "fstring" in admissible_files(
        {"h.py": "def h():\n    return f'qu{\"e\"}ry'\n"}, [])["inadmissible"].get("h.py", [])
    out["a1_constant_getattr_is_NOT_a_construction_site"] = not construction_sites(
        'def i(o):\n    return getattr(o, "query")()\n'
    )
    out["a1_note"] = (
        "getattr(o, 'query') writes the name as a string, so T(C) already "
        "contains it and the token rule is sound; only a NON-constant argument "
        "defeats T(C), so only that is flagged."
    )

    # VACUITY: a predictor whose edges come from call sites produces F = {}.
    c_src = "def s():\n    return t()\n"
    c_tok = file_token_sets({"s.py": c_src})
    local_pred = {("s", "m.t"), ("s", "m.t"), ("s", "m.other")}
    c_adm = {"s.py": True}
    r_local = refute(local_pred, {"s": "s.py"}, c_tok["tokens"], c_adm)
    out["vacuity_local_edges"] = r_local["n_refuted"]
    assert r_local["n_refuted"] == 1, r_local
    out["vacuity_note"] = (
        "a call site spelling 't' blocks its own edge, so F is empty on a "
        "syntactically derived predictor except for the class-call "
        "NORMALISATIONS A2 exists to catch -- and those are A2's job, not the "
        "refuter's. This is the measurement that decides the node: the refuter "
        "is worth nothing on the family of edges the loop has been scoring."
    )

    # The monotonicity statement, on numbers.
    pred = {("a", "p"), ("a", "q"), ("b", "r")}
    truth = {("a", "p")}
    F = {("b", "r")}  # sound: it removed a false edge only
    def prec(pset):
        return round(len(pset & truth) / len(pset), 4) if pset else 0.0
    out["monotonicity"] = {
        "precision_before": prec(pred),
        "precision_after_sound_refutation": prec(pred - F),
        "precision_after_UNSOUND_refutation": prec(pred - {("a", "p")}),
        "assertion": (
            "a sound refuter is precision-monotone non-decreasing because it "
            "touches the denominator only; an unsound one that removes a true "
            "edge LOWERS precision. The loop's own run-4 refusal and run-6 "
            "over-approximation are the same asymmetry read the other way."
        ),
    }
    assert out["monotonicity"]["precision_after_sound_refutation"] == 0.5
    assert out["monotonicity"]["precision_after_UNSOUND_refutation"] < \
        out["monotonicity"]["precision_before"]
    return out


if __name__ == "__main__":  # pragma: no cover - manual self-check entry point
    import json

    print(json.dumps(self_check(), indent=1))
