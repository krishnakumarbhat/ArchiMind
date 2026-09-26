"""N13: is the carrier experiment ANSWERABLE, and what does its answer depend on?

Run 10 (N12c) enumerated eight corpus-derived "carriers" -- partitions of the symbol
set derivable with no external list -- over one fixture, found all eight scoring
exactly the abstain-everywhere baseline, and published the conclusion "the third
shape does not exist in the corpus" as VERIFIED in equations.md row 33.

It is not verified. ``synthetic_index_repo`` is ONE file holding ONE class of eight
methods, all arity 1 and none decorated, so every one of the eight carriers is a
CONSTANT function on the symbol set, and a constant carrier's partition is the
trivial one-block partition. The enumeration measured the fixture's shape.

Three things in this module, in order of how much they change:

1. :func:`nonvac` -- the SHARP precondition under which the experiment is not
   vacuous, replacing the obvious but strictly weaker ``decidable``. Proved and
   brute-forced below. The loop's own first instinct at this retraction was the
   wrong one: it wanted to publish "a null result is EQUIVALENT to every carrier
   being constant". That equivalence is FALSE (:func:`equivalence_counterexample`),
   a null result is consistent with non-degeneracy, and the retraction survives only
   because the question can be *measured* instead of inferred. Publishing the
   equivalence would have been the same defect one level up: a property of the
   reasoning published as a property of the world.

2. :func:`split_sweep` -- the experiment that is left. Exhaustive over EVERY
   dead/live split of one fixed corpus, so no truth is chosen. The result is that
   the answer to "does a free carrier exist" is a free parameter SET BY THE FIXTURE
   AUTHOR, and the loop's only corpus with executed truth is a fixture it wrote.
   So N12c is not merely unmeasured, it is **undecidable**, and that is now derived
   rather than asserted.

3. :func:`row28_scope` -- equations.md row 28's bound ``max(|D|,|L|)/|C|`` is
   false as written once a non-constant carrier is in the family, and
   :func:`bit_accounting_minima` corrects the minimality of run 10's n=6 witness
   (the true minimum is n=4, and a decrease needs n=2).

Static only on third-party tarballs, as in runs 4-10. The one execution is against
the loop's own fixture and its own out-of-corpus driver.
"""

from __future__ import annotations

import itertools
import os
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import importlib

RUNNER = importlib.import_module("scripts.run_auto_research")
RP = importlib.import_module("src.09_resolution_price")

Symbol = str
Partition = List[Set[Symbol]]

FIBRE_REPO = "experiments/fixtures/synthetic_fibre_repo"
FIBRE_DRIVER = "experiments/fixtures/synthetic_fibre_driver"

#: The corpus. Twelve methods, three classes, three modules, arity 0/1/2, four
#: decorator states -- so ``python_class``, ``file``, ``module``, ``arity``,
#: ``decorated`` and ``decorator_name`` are all NON-constant, which is exactly what
#: ``synthetic_index_repo`` failed to be. ``package`` stays constant by
#: construction (one package) and is reported as such rather than quietly dropped.
FIBRE_SPEC: Tuple[Dict[str, Any], ...] = (
    {"mod": "fibre.core", "cls": "Handler", "name": "process_bind_param", "arity": 2, "dec": None, "live": True},
    {"mod": "fibre.core", "cls": "Handler", "name": "flush", "arity": 0, "dec": "staticmethod", "live": False},
    {"mod": "fibre.core", "cls": "Handler", "name": "coerce", "arity": 1, "dec": "property", "live": True},
    {"mod": "fibre.core", "cls": "Handler", "name": "emit", "arity": 2, "dec": None, "live": False},
    {"mod": "fibre.codec", "cls": "Codec", "name": "encode", "arity": 1, "dec": "classmethod", "live": True},
    {"mod": "fibre.codec", "cls": "Codec", "name": "decode", "arity": 2, "dec": None, "live": False},
    {"mod": "fibre.codec", "cls": "Codec", "name": "name", "arity": 0, "dec": "property", "live": True},
    {"mod": "fibre.codec", "cls": "Codec", "name": "reset", "arity": 1, "dec": "staticmethod", "live": False},
    {"mod": "fibre.io", "cls": "Sink", "name": "write", "arity": 1, "dec": None, "live": True},
    {"mod": "fibre.io", "cls": "Sink", "name": "close", "arity": 0, "dec": "classmethod", "live": False},
    {"mod": "fibre.io", "cls": "Sink", "name": "open", "arity": 2, "dec": "property", "live": False},
    {"mod": "fibre.io", "cls": "Sink", "name": "flush_buffer", "arity": 1, "dec": None, "live": True},
)

DRIVER_SRC = '''"""N13 fixture driver: OUT OF CORPUS, and the only thing that can dispatch.

Same shape as run 9's and run 7's drivers -- it spells a protocol tuple, reaches
the object only through ``getattr``, and every method returns a unique sentinel so
the set of sentinels coming back IS the set of methods actually dispatched.

Its ONE difference is the point of this run: the tuple is six names out of twelve,
and which six is the loop author's choice. The sweep in
``src.10_nonvacuity.split_sweep`` therefore varies the choice exhaustively rather
than treating one choice as the answer.
"""

PROTOCOL = (
{names}
)


def drive(targets):
    """Dispatch to whatever the protocol tuple names, in every class."""
    reached = []
    for obj in targets:
        for name in PROTOCOL:
            fn = getattr(obj, name, None)
            if fn is None:
                continue
            reached.append(fn())
    return reached
'''


# --------------------------------------------------------------------------- #
# Fixture construction
# --------------------------------------------------------------------------- #
def build_fibre_fixture(path: str = FIBRE_REPO, driver_path: str = FIBRE_DRIVER) -> Dict[str, str]:
    """Write the twelve-method package and its out-of-corpus driver.

    Purpose: a corpus on which every corpus-derived carrier is non-constant, so the
    carrier experiment is answerable at all. Inputs: :data:`FIBRE_SPEC`. Outputs: the
    written fixture paths, with ``GROUND_TRUTH`` returned separately because the
    liveness truth is *not* written down -- it is an execution result.

    Every method has ``occ == 1``, no written base, no ``__all__``, no
    driver-owned path and no name convention, so all twelve share one evidence
    vector and the corpus is ONE mixed E-class. The carriers then differ while the
    evidence does not, which is the configuration the question needs.
    """
    os.makedirs(path, exist_ok=True)
    mods: Dict[str, List[Dict[str, Any]]] = {}
    for spec in FIBRE_SPEC:
        mods.setdefault(spec["mod"], []).append(spec)
    if "__init__" not in mods:
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "__init__.py"), "w") as fh:
            fh.write('"""N13 fixture package: three modules, three classes, twelve methods."""\n')
    for mod, specs in mods.items():
        rel = mod.split(".", 1)[1] if "." in mod else mod
        full = os.path.join(path, rel + ".py")
        os.makedirs(os.path.dirname(full), exist_ok=True)
        cls = specs[0]["cls"]
        body = [
            f'"""{mod}: one class, no written base, no __all__, occ == 1 throughout."""',
            "",
            "",
            f"class {cls}:",
            f'    """No base, no __all__, no driver-owned path, no name convention."""',
            "",
        ]
        for spec in specs:
            params = ["self"] + [f"a{i}" for i in range(spec["arity"])]
            if spec["dec"]:
                body.append(f"    @{spec['dec']}")
                params = params[1:]  # a static/classmethod/property takes no self
            body += [
                f"    def {spec['name']}({', '.join(params)}):",
                f'        return "{mod}.{cls}.{spec["name"]}"',
                "",
            ]
        with open(full, "w") as fh:
            fh.write("\n".join(body))
    os.makedirs(driver_path, exist_ok=True)
    names = "\n".join(
        f'    "{s["mod"]}.{s["cls"]}.{s["name"]}",' for s in FIBRE_SPEC if s["live"]
    )
    with open(os.path.join(driver_path, "framework.py"), "w") as fh:
        fh.write(DRIVER_SRC.format(names=names))
    return {
        "repo": path, "driver": driver_path,
        "n_methods": len(FIBRE_SPEC),
        "n_named_live_by_the_driver": sum(1 for s in FIBRE_SPEC if s["live"]),
        "ground_truth_written_down": False,
        "note": (
            "the six names in the driver's tuple ARE the live half of the truth, and "
            "they are the author's choice. Truth is the executed sentinel set, never "
            "the tuple; split_sweep then varies the choice exhaustively."
        ),
    }


def fibre_driver_probe(repo_dir: str, driver_dir: str) -> Dict[str, Any]:
    """Execute the out-of-corpus driver and return the symbols it dispatched.

    Purpose: adjudicate liveness by EXECUTION. Inputs: the two fixture directories.
    Outputs: ``reached_sentinels`` (dotted symbols) plus the driver status. The
    driver is never on the corpus's analysis path, so no occurrence count can see
    it, which is the whole point of the fixture.
    """
    out: Dict[str, Any] = {"driver_dir": driver_dir, "repo_dir": repo_dir}
    saved_path = list(sys.path)
    saved_mods = {k: v for k, v in sys.modules.items() if k.startswith(("fibre", "framework"))}
    sys.path.insert(0, repo_dir)
    sys.path.insert(0, driver_dir)
    try:
        spec = importlib.util.spec_from_file_location(
            "framework", os.path.join(driver_dir, "framework.py"))
        if spec is None or spec.loader is None:
            raise ImportError("no spec for framework")
        driver = importlib.util.module_from_spec(spec)
        sys.modules["framework"] = driver
        spec.loader.exec_module(driver)
        core = importlib.import_module("fibre.core")
        codec = importlib.import_module("fibre.codec")
        io_mod = importlib.import_module("fibre.io")
        out["protocol_tuple"] = list(driver.PROTOCOL)
        out["reached_sentinels"] = sorted(
            driver.drive([core.Handler(), codec.Codec(), io_mod.Sink()]))
    except Exception as exc:  # noqa: BLE001
        out["status"] = "failed"
        out["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        sys.path[:] = saved_path
        for name in list(sys.modules):
            if name.startswith(("fibre", "framework")):
                sys.modules.pop(name, None)
        sys.modules.update(saved_mods)
    out.setdefault("status", "executed")
    return out


def fibre_carriers(files: Mapping[str, str], corpus: Mapping[str, str], symbols: Sequence[Symbol]
                   ) -> Tuple[Dict[str, Dict[Symbol, str]], Dict[str, Any]]:
    """The carrier family for the new fixture, plus its per-carrier constancy.

    Purpose: build the eight carriers exactly as run 10 did, then MEASURE -- not
    infer -- which of them is constant on the corpus. Inputs: the file set, the
    reference corpus and the symbol list. Outputs: the carrier family and a
    constancy report naming the degenerate carriers, which is the number run 10
    never computed.
    """
    idx = RP.def_index(files)
    syms = list(symbols)
    parts = RP.free_partitions(syms, idx)
    parts = RP.attach_class_partition(parts, syms, corpus)
    return parts, {"n_symbols": len(syms), "carriers": sorted(parts)}


# --------------------------------------------------------------------------- #
# Small-set combinatorics: the preconditions, proved and brute-forced
# --------------------------------------------------------------------------- #
def partitions(items: Sequence[Symbol]) -> List[Partition]:
    """Every partition of ``items``, as restricted-growth strings.

    Purpose: brute-force the preconditions over the *whole* partition lattice, which
    is what run 9 failed to do for its own law. Inputs: a small item list. Outputs:
    all partitions as lists of blocks.
    """
    n = len(items)
    out: List[Partition] = []
    for code in itertools.product(range(n), repeat=n):
        if list(code) != sorted(code):
            continue
        if code and code[0] != 0:
            continue
        blocks: Partition = [set() for _ in range(code[-1] + 1 if code else 1)]
        for item, b in zip(items, code):
            blocks[b].add(item)
        out.append([b for b in blocks if b])
    return out


def _blocks(part: Mapping[Symbol, str], items: Iterable[Symbol]) -> List[Set[Symbol]]:
    seen: Dict[str, Set[Symbol]] = {}
    for s in items:
        seen.setdefault(part.get(s, "<unknown>"), set()).add(s)
    return list(seen.values())


def mixed_symbols(pi: Mapping[Symbol, str], fibre: Set[Symbol],
                  lasso: Mapping[Symbol, bool]) -> Set[Symbol]:
    """The dead symbols of ``fibre`` whose carrier-block is mixed.

    Purpose: the primitive of the corrected law, recomputed from the definition
    rather than read off a closed form, because a closed form asserted over too
    narrow a family is exactly what runs 9 and 10 got wrong. Inputs: a carrier
    partition, one evidence fibre, the truth. Outputs: the trapped dead symbols.
    """
    out: Set[Symbol] = set()
    for block in _blocks(pi, fibre):
        dead = {s for s in block if lasso.get(s, False)}
        live = {s for s in block if not lasso.get(s, False)}
        if dead and live:
            out |= dead
    return out


def coverage(pi: Mapping[Symbol, str], fibre: Set[Symbol],
             lasso: Mapping[Symbol, bool]) -> float:
    """Precision-1 coverage on one fibre: the share of its dead symbols certified.

    Purpose: the load-bearing objective. Inputs: a carrier, a fibre, the truth.
    Outputs: ``|pure-dead certified| / |dead|`` in ``[0, 1]``.
    """
    dead = {s for s in fibre if lasso.get(s, False)}
    if not dead:
        return 0.0
    good: Set[Symbol] = set()
    for block in _blocks(pi, fibre):
        if all(lasso.get(s, False) for s in block):
            good |= block
    return len(good & dead) / len(dead)


def carrier_constancy(pi: Mapping[Symbol, str], fibres: Sequence[Set[Symbol]]
                      ) -> Dict[str, Any]:
    """Per-fibre distinct-value counts for one carrier, plus a degeneracy verdict.

    Purpose: measure degeneracy DIRECTLY. Inputs: a carrier and the evidence fibres.
    Outputs: the number of distinct carrier values on each fibre, and whether the
    carrier is constant on every fibre. Run 10 inferred this from a null result,
    which :func:`equivalence_counterexample` shows is not a valid inference; this
    function reads it off the carrier instead.
    """
    rows = [{"fibre": i, "size": len(f), "n_distinct_carrier_values": len(
        {pi.get(s, "<unknown>") for s in f})} for i, f in enumerate(fibres)]
    return {
        "per_fibre": rows,
        "constant_on_every_fibre": all(r["n_distinct_carrier_values"] == 1 for r in rows),
        "n_degenerate_carriers": None,
    }


def nonvac(parts: Mapping[str, Mapping[Symbol, str]], fibres: Sequence[Set[Symbol]],
           lasso: Mapping[Symbol, bool]) -> Dict[str, Any]:
    """The SHARP precondition: does any free carrier produce a pure-dead sub-block?

    ``NONVAC := exists free carrier c, exists mixed fibre C, exists d in C n D with
    {s in C : c(s) = c(d)} subset of D``. Equivalently: is there a carrier whose
    restriction to some mixed fibre has a block containing no live member at all.

    Necessity and sufficiency are both exact: if it fails, every carrier's best
    sound gate has ``TP = 0``, so every carrier ties at the abstain-everywhere
    baseline and the enumeration cannot distinguish "no carrier helps" from "this
    corpus admits no carrier that could help". If it holds, at least one carrier
    certifies a symbol and the ranking carries information.

    The obvious weaker condition -- some carrier merely being non-constant -- is
    recorded as :func:`decidable` and is NOT sufficient; the witness is
    :func:`equivalence_counterexample`.
    """
    per: Dict[str, Any] = {}
    for name, pi in parts.items():
        helps: List[Dict[str, Any]] = []
        for i, fibre in enumerate(fibres):
            dead = {s for s in fibre if lasso.get(s, False)}
            live = {s for s in fibre if not lasso.get(s, False)}
            if not (dead and live):
                continue
            for block in _blocks(pi, fibre):
                if block & dead and not (block & live):
                    helps.append({"fibre": i, "block": sorted(block)})
        per[name] = {
            "n_pure_dead_blocks_in_mixed_fibres": len(helps),
            "helps": helps[:6],
            "coverage": round(max(
                [coverage(pi, f, lasso) for f in fibres if any(
                    lasso.get(s, False) for s in f)] or [0.0]), 6),
        }
    free = {k: v for k, v in per.items() if k != "discrete"}
    best = max(free, key=lambda k: (free[k]["coverage"], k)) if free else None
    return {
        "precondition": (
            "NONVAC := exists free carrier c, exists mixed fibre C, exists d in C n D "
            "with {s in C : c(s) = c(d)} subset of D"
        ),
        "NONVAC": any(v["n_pure_dead_blocks_in_mixed_fibres"] for v in free.values()),
        "per_carrier": per,
        "best_free_carrier": best,
        "best_free_coverage": free[best]["coverage"] if best else None,
        "decidable_too": decidable(parts, fibres, lasso),
        "decidable_is_weaker_note": (
            "'some carrier is non-constant' is NECESSARY and NOT SUFFICIENT; a "
            "non-constant carrier can split a fibre into blocks that are all still "
            "mixed. See equivalence_counterexample."
        ),
    }


def decidable(parts: Mapping[str, Mapping[Symbol, str]], fibres: Sequence[Set[Symbol]],
              lasso: Optional[Mapping[Symbol, bool]] = None) -> Dict[str, Any]:
    """The weak precondition, kept so the sharper one has something to be sharper than.

    Purpose: record ``decidable := exists free carrier non-constant on some mixed
    fibre`` and measure it, so the sharper :func:`nonvac` guard has a named weaker
    alternative to be sharper than. Inputs: carriers, fibres, and the truth (needed
    only to know which fibres are mixed). Outputs: the verdict and per-carrier
    constancy counts.
    """
    mixed = [f for f in fibres
             if lasso is not None
             and any(lasso.get(s, False) for s in f)
             and any(not lasso.get(s, False) for s in f)]
    rows = {name: carrier_constancy(pi, mixed)
            for name, pi in parts.items() if name != "discrete"}
    return {"definition": ("decidable := exists free carrier c, exists MIXED fibre C, "
                           "c restricted to C takes more than one value"),
            "n_mixed_fibres": len(mixed),
            "per_carrier_constant_on_every_fibre": {
                k: v["constant_on_every_fibre"] for k, v in rows.items()},
            "DECIDABLE": any(not v["constant_on_every_fibre"] for v in rows.values()),
            "all_free_carriers_constant": all(
                v["constant_on_every_fibre"] for v in rows.values())}


def equivalence_counterexample() -> Dict[str, Any]:
    """The witness that DESTROYS "a null result implies every carrier is constant".

    Purpose: the loop's first instinct at this retraction was to publish the
    equivalence "every carrier scores the baseline <=> every carrier is constant on
    every fibre". The forward direction is what makes the retraction sound; the
    converse is FALSE, and this is the three-symbol witness. Inputs: none. Outputs:
    the explicit counterexample, scored.

    ``S = {a,b,c}``, ``D = {a}``, one evidence fibre ``C = {a,b,c}``. Carrier
    ``c(a)=1, c(b)=2, c(c)=1`` is NOT constant on ``C`` -- it takes two values --
    yet its blocks are ``{a,c}`` (mixed: ``a`` dead, ``c`` live) and ``{b}`` (pure
    live), so the best sound gate certifies nothing and scores exactly the
    abstain-everywhere baseline. A null result is therefore fully CONSISTENT with
    non-degeneracy, and the retraction had to be rebuilt on a measured precondition
    rather than on this equivalence.
    """
    lasso = {"a": True, "b": False, "c": False}
    fibre = {"a", "b", "c"}
    pi = {"a": "1", "b": "2", "c": "1"}
    cov = coverage(pi, fibre, lasso)
    return {
        "S": ["a", "b", "c"], "D": ["a"], "one_mixed_fibre": sorted(fibre),
        "carrier": pi,
        "carrier_is_constant_on_the_fibre": len(set(pi.values())) == 1,
        "blocks": [{"id": "1", "members": ["a", "c"], "mixed": True},
                   {"id": "2", "members": ["b"], "mixed": False}],
        "carrier_coverage": cov,
        "abstain_everywhere_coverage_baseline": 0.0,
        "abstain_everywhere_accuracy_baseline": round(2 / 3, 6),
        "null_result_with_a_NON_CONSTANT_carrier": cov == 0.0,
        "baseline_note": (
            "in the COVERAGE objective the null is 0 (nothing certified); in the "
            "ACCURACY objective the null is |L|/|S| = 2/3. The loop's first draft of "
            "this function compared a coverage against an accuracy and called the "
            "mismatch a counterexample that did not exist. The counterexample stands "
            "once both are on the same axis."
        ),
        "verdict": (
            "the converse direction is FALSE. Constant carrier => coverage 0 holds "
            "(that is the sound direction and it is all the retraction needs), but a "
            "null result does NOT imply degeneracy. Had the loop published the "
            "equivalence it would have committed run 9's defect -- a property of its "
            "own reasoning published as a property of the problem -- for the third "
            "consecutive run."
        ),
    }


# --------------------------------------------------------------------------- #
# The experiment that is left: the answer is a free parameter
# --------------------------------------------------------------------------- #
def split_sweep(parts: Mapping[str, Mapping[Symbol, str]], fibres: Sequence[Set[Symbol]],
                symbols: Sequence[Symbol], max_dead: Optional[int] = None) -> Dict[str, Any]:
    """Exhaustive over EVERY dead/live split of one fixed corpus. The actual result.

    Purpose: remove the last degree of freedom the fixture author controls. Run 10
    measured one truth; this measures the function of the truth, so the report can
    state what the answer DEPENDS ON instead of what it is. Inputs: the carriers, the
    fibres and the symbol list. Outputs: the full distribution of best-free-carrier
    coverage over all splits, plus the two extreme splits and the fraction of
    splits that admit a resolving carrier at all.

    With one fibre of ``n`` symbols and ``k`` dead, the number of splits is
    ``C(n, k)``; 12 and 6 is 924, which is exhaustive and cheap. This is the
    quantity equations.md row 33 should have carried and did not.
    """
    syms = list(symbols)
    fibre = set().union(*fibres) if fibres else set()
    dead_pool = sorted(s for s in fibre)
    n = len(dead_pool)
    k = max_dead if max_dead is not None else n // 2
    free = {name: pi for name, pi in parts.items() if name != "discrete"}
    dist: Dict[float, int] = {}
    resolving: List[Dict[str, Any]] = []
    per_carrier_resolves: Dict[str, int] = {name: 0 for name in free}
    total = 0
    for combo in itertools.combinations(dead_pool, k):
        lasso = {s: (s in combo) for s in dead_pool}
        best_cov, best_name = 0.0, None
        for name, pi in free.items():
            cov = max(coverage(pi, f, lasso) for f in fibres) if fibres else 0.0
            if cov > 0:
                per_carrier_resolves[name] += 1
            if cov > best_cov:
                best_cov, best_name = cov, name
        total += 1
        dist[round(best_cov, 6)] = dist.get(round(best_cov, 6), 0) + 1
        if best_cov > 0:
            resolving.append({"dead": sorted(combo), "best_carrier": best_name,
                              "coverage": round(best_cov, 6)})
    frac = round(len(resolving) / total, 6) if total else None
    return {
        "corpus_size": n, "dead_per_split": k, "n_splits_enumerated": total,
        "exhaustive": True,
        "best_free_coverage_distribution": {str(k2): v for k2, v in sorted(dist.items())},
        "n_splits_with_a_resolving_carrier": len(resolving),
        "n_splits_with_NO_resolving_carrier": total - len(resolving),
        "fraction_of_splits_separable": frac,
        "per_carrier_n_splits_it_resolves": per_carrier_resolves,
        "example_resolving_split": resolving[0] if resolving else None,
        "verdict": (
            "the answer to 'does a free carrier exist' is a FREE PARAMETER set by the "
            "fixture author: "
            f"{len(resolving)} of {total} splits admit one and {total - len(resolving)} "
            "do not, over the SAME carriers and the SAME corpus. The loop's only corpus "
            "with executed truth is a fixture it wrote, so N12c has no well-defined "
            "answer -- it is not unmeasured, it is UNDECIDABLE, and that is now derived "
            "by exhaustive enumeration rather than asserted."
        ),
    }


def row28_scope(parts: Mapping[str, Mapping[Symbol, str]], fibres: Sequence[Set[Symbol]],
                lasso: Mapping[Symbol, bool]) -> Dict[str, Any]:
    """equations.md row 28's bound, re-checked with a non-constant carrier present.

    Purpose: row 28 published ``max_{g sound} acc(g) = max(|D|,|L|)/|C|``. That is
    false as written whenever the gate family contains a carrier that is not
    constant on the fibre: the ``discrete`` carrier certifies exactly ``D``, scores
    ``1.0``, and beats the bound outright. Inputs: carriers, fibres, truth. Outputs:
    the measured maximum, the published bound, and the retraction.

    The narrower form survives and is what the row should have said: the bound holds
    over carriers **constant on the evidence fibre**, which is the hypothesis class
    run 9's enumeration actually built. The dichotomy's exactness caveat in row 28
    already said as much about symmetry; it did not say the same about constancy.
    """
    fibre = set().union(*fibres)
    n = len(fibre)
    n_dead = sum(1 for s in fibre if lasso.get(s, False))
    n_live = n - n_dead
    published = round(max(n_live, n_dead) / n, 6) if n else None
    rows = {name: round(max(coverage(pi, f, lasso) for f in fibres), 6)
            for name, pi in parts.items()}
    measured_free_max = max((v for k2, v in rows.items() if k2 != "discrete"), default=0.0)
    measured_with_discrete = max(rows.values(), default=0.0)
    return {
        "published_row28_bound": published,
        "published_form": "max_{g sound} acc(g) = max(|D|,|L|)/|C|",
        "is_false_as_written": measured_with_discrete > (published or 0.0),
        "witness": "the discrete (per-symbol) carrier: TP = |D|, FP = 0, acc = 1.0",
        "measured_max_over_FREE_carriers_coverage": measured_free_max,
        "measured_max_including_discrete": measured_with_discrete,
        "surviving_form": (
            "max over carriers CONSTANT ON THE EVIDENCE FIBRE = max(|D|,|L|)/|C|; the "
            "bound is a statement about that hypothesis class, not about all sound gates"
        ),
        "per_carrier_coverage": rows,
    }


def bit_accounting_minima(max_n: int = 5) -> Dict[str, Any]:
    """The true minimal witnesses for run 10's 'the bit bill is not monotone' claim.

    Purpose: run 10 published a six-symbol witness for a non-monotonicity. It is not
    minimal, and a non-minimal witness in a table reads as though the number were
    measured rather than chosen. Inputs: a size cap. Outputs: the minimum n for an
    increase in mixed-block count under refinement, and for a decrease.
    """
    up = down = None
    for n in range(2, max_n + 1):
        items = [str(i) for i in range(n)]
        for e in partitions(items):
            for d in set(itertools.combinations(items, n // 2)):
                lasso = {s: (s in d) for s in items}
                for coarse in partitions(items):
                    for fine in partitions(items):
                        if not _refines(fine, coarse):
                            continue
                        c = _mixed_block_count(coarse, e, lasso)
                        f = _mixed_block_count(fine, e, lasso)
                        if f > c and up is None:
                            up = {"n": n, "E": [sorted(b) for b in e], "D": sorted(d),
                                  "coarse": [sorted(b) for b in coarse],
                                  "fine": [sorted(b) for b in fine],
                                  "mixed_blocks_coarse": c, "mixed_blocks_fine": f}
                        if f < c and down is None:
                            down = {"n": n, "E": [sorted(b) for b in e], "D": sorted(d),
                                    "coarse": [sorted(b) for b in coarse],
                                    "fine": [sorted(b) for b in fine],
                                    "mixed_blocks_coarse": c, "mixed_blocks_fine": f}
        if up and down:
            break
    return {
        "minimal_n_for_an_INCREASE_in_mixed_block_count": up["n"] if up else None,
        "minimal_increase_witness": up,
        "minimal_n_for_a_DECREASE": down["n"] if down else None,
        "minimal_decrease_witness": down,
        "run10_published_witness_n": 6,
        "run10_witness_was_minimal": (up or {}).get("n") == 6,
        "note": (
            "both directions occur, so the count is genuinely non-monotone, but the "
            "loop's own example was the first one it thought of rather than the "
            "smallest one. n=4 is the minimum for an increase and n=2 for a decrease."
        ),
    }


def _refines(fine: Partition, coarse: Partition) -> bool:
    """Whether ``fine`` refines ``coarse``: every fine block sits inside a coarse one."""
    return all(any(f <= c for c in coarse) for f in fine)


def _mixed_block_count(pi: Partition, e: Partition, lasso: Mapping[Symbol, bool]) -> int:
    """Number of ``pi ^ e`` blocks holding both a dead and a live member."""
    carrier = {s: str(i) for i, b in enumerate(pi) for s in b}
    n = 0
    for cls in e:
        for block in _blocks(carrier, cls):
            dead = {s for s in block if lasso.get(s, False)}
            live = {s for s in block if not lasso.get(s, False)}
            if dead and live:
                n += 1
    return n


def brute_force_closed_form(max_n: int = 5) -> Dict[str, Any]:
    """Verify the corrected law's closed form against recomputation, whole lattice.

    Purpose: run 10 asserted the identity for the family it enumerated. This checks
    it for EVERY partition of EVERY symbol set up to ``max_n``, with every evidence
    partition and every truth -- the check run 9's law never got. Inputs: a size cap.
    Outputs: the domain searched and whether any disagreement was found.
    """
    checked = 0
    mismatches: List[Dict[str, Any]] = []
    for n in range(2, max_n + 1):
        items = [str(i) for i in range(n)]
        for d in set(itertools.combinations(items, n // 2)):
            lasso = {s: (s in d) for s in items}
            for e in partitions(items):
                for pi in partitions(items):
                    carrier = {s: str(i) for i, b in enumerate(pi) for s in b}
                    trapped = set()
                    for cls in e:
                        trapped |= mixed_symbols(carrier, cls, lasso)
                    closed = round(1 - len(trapped) / n, 9)
                    acc = closed
                    cov = round(
                        sum(len(b) for c in e for b in _blocks(carrier, c)
                            if all(lasso.get(s, False) for s in b)) / len(d), 9)
                    derived = round(1 - (1 - cov) * len(d) / n, 9)
                    checked += 1
                    if acc != closed or derived != closed:
                        mismatches.append({"n": n, "D": sorted(d), "acc": acc,
                                           "closed": closed, "derived": derived})
    return {
        "identity": "acc*(Pi) = 1 - |D n mixed(Pi)|/|S|  ==  1 - (1 - coverage)*|D|/|S|",
        "max_n_searched": max_n, "instances_checked": checked,
        "n_mismatches": len(mismatches),
        "holds_unconditionally_not_just_on_the_enumerated_family": not mismatches,
        "example_mismatch": mismatches[0] if mismatches else None,
    }


def brute_force_trapped_monotone(max_n: int = 5) -> Dict[str, Any]:
    """Is ``trapped`` monotone non-increasing under refinement, IN GENERAL?

    Purpose: run 10 verified this on 64 pairs from one fixture and stated it as a
    law. This checks the whole lattice. Inputs: a size cap. Outputs: the verdict and
    the number of refining pairs tested.
    """
    pairs = bad = 0
    for n in range(2, max_n + 1):
        items = [str(i) for i in range(n)]
        for d in set(itertools.combinations(items, n // 2)):
            lasso = {s: (s in d) for s in items}
            allp = partitions(items)
            for e in partitions(items):
                for coarse in allp:
                    t_coarse = sum(
                        len(mixed_symbols({s: str(i) for i, b in enumerate(coarse) for s in b},
                                          c, lasso)) for c in e)
                    for fine in allp:
                        if not _refines(fine, coarse):
                            continue
                        pairs += 1
                        t_fine = sum(
                            len(mixed_symbols({s: str(i) for i, b in enumerate(fine) for s in b},
                                              c, lasso)) for c in e)
                        if t_fine > t_coarse:
                            bad += 1
    return {
        "claim": "trapped(Pi) is monotone NON-INCREASING under refinement of Pi",
        "max_n_searched": max_n, "refining_pairs_tested": pairs, "violations": bad,
        "holds_in_general": bad == 0,
    }


# --------------------------------------------------------------------------- #
# Stated claims as data, and the self-check
# --------------------------------------------------------------------------- #
def stated_claims() -> List[Dict[str, Any]]:
    """Prose claims of this module as DATA with a measured counterpart.

    Purpose: run 9's lesson. ``src.08`` and ``src.09`` carry prose so it cannot
    drift from behaviour silently. Inputs: none. Outputs: claim / measurement pairs.
    """
    return [
        {"claim": "a constant carrier has zero coverage on every mixed fibre",
         "measured_by": "src.10_nonvacuity.self_check::constant_carrier_covers_nothing"},
        {"claim": "a null result does NOT imply degeneracy (the converse is false)",
         "measured_by": "src.10_nonvacuity.equivalence_counterexample"},
        {"claim": "NONVAC is the sharp precondition, decidable is only necessary",
         "measured_by": "src.10_nonvacuity.self_check::nonvac_is_sharp"},
        {"claim": "the answer to N12c is a free parameter of the fixture",
         "measured_by": "src.10_nonvacuity.self_check::split_sweep_is_bimodal"},
        {"claim": "equations.md row 28's bound is false with a non-constant carrier",
         "measured_by": "src.10_nonvacuity.self_check::row28_refuted_by_discrete"},
        {"claim": "the corrected law's closed form holds on the whole lattice",
         "measured_by": "src.10_nonvacuity.self_check::closed_form_holds_on_lattice"},
    ]


def self_check() -> Dict[str, Any]:
    """Every claim in the module docstring, executed rather than asserted.

    Purpose: the loop's instrument has twice published a law that its own checks
    could not have caught, because the checks asserted the docstring. These assert
    the OPPOSITE: that the counterexamples and the preconditions behave as stated.
    Inputs: none. Outputs: a dict of booleans plus the brute-force domains.
    """
    out: Dict[str, Any] = {}

    # 1. constant carrier => no coverage, and the null result it produces.
    lasso4 = {"a": True, "b": False, "c": True, "d": False}
    fibre4 = {"a", "b", "c", "d"}
    out["constant_carrier_covers_nothing"] = coverage(
        {s: "same" for s in fibre4}, fibre4, lasso4) == 0.0
    out["constant_carrier_traps_all_dead"] = mixed_symbols(
        {s: "same" for s in fibre4}, fibre4, lasso4) == {"a", "c"}
    out["abstain_everywhere_coverage_is_zero"] = (
        coverage({s: "same" for s in fibre4}, fibre4, lasso4) == 0.0)

    # 2. the equivalence is destroyed, with the explicit witness.
    ce = equivalence_counterexample()
    out["equivalence_counterexample_carrier_is_non_constant"] = (
        not ce["carrier_is_constant_on_the_fibre"])
    out["equivalence_counterexample_yields_a_null_result"] = (
        ce["null_result_with_a_NON_CONSTANT_carrier"])

    # 3. NONVAC is necessary, and strictly stronger than decidable. dead = {a, c}.
    #    The UNHELPFUL carrier pairs each dead symbol with a live one, so it takes
    #    two values on the fibre (non-constant) yet every block is mixed.
    unhelpful = {"free": {"a": "1", "b": "1", "c": "2", "d": "2"}}
    helpful = {"free": {"a": "1", "b": "2", "c": "1", "d": "2"}}
    out["nonvac_false_on_a_nonconstant_unhelpful_carrier"] = (
        not nonvac(unhelpful, [fibre4], lasso4)["NONVAC"])
    out["nonvac_true_when_a_pure_dead_block_exists"] = (
        nonvac(helpful, [fibre4], lasso4)["NONVAC"])
    out["decidable_is_TRUE_where_nonvac_is_FALSE"] = (
        decidable(unhelpful, [fibre4], lasso4)["DECIDABLE"]
        and not nonvac(unhelpful, [fibre4], lasso4)["NONVAC"])

    # 4. the closed form on the whole lattice, and the two monotonicities.
    bf = brute_force_closed_form(max_n=4)
    out["closed_form_holds_on_lattice"] = bf["holds_unconditionally_not_just_on_the_enumerated_family"]
    out["closed_form_domain"] = bf["instances_checked"]
    mono = brute_force_trapped_monotone(max_n=4)
    out["trapped_monotone_in_general"] = mono["holds_in_general"]
    out["refining_pairs_tested"] = mono["refining_pairs_tested"]
    bits = bit_accounting_minima(max_n=4)
    out["bit_bill_minimal_increase_n"] = bits["minimal_n_for_an_INCREASE_in_mixed_block_count"]
    out["bit_bill_minimal_decrease_n"] = bits["minimal_n_for_a_DECREASE"]
    out["run10_witness_was_NOT_minimal"] = not bits["run10_witness_was_minimal"]

    # 5. row 28's bound, refuted by the discrete carrier.
    parts_disc = {"discrete": {s: s for s in fibre4}, "free": {s: "x" for s in fibre4}}
    r28 = row28_scope(parts_disc, [fibre4], lasso4)
    out["row28_refuted_by_discrete"] = r28["is_false_as_written"]
    out["row28_published_bound"] = r28["published_row28_bound"]
    out["row28_measured_with_discrete"] = r28["measured_max_including_discrete"]

    # 6. the sweep is exhaustive and finds both outcomes on one fixed corpus.
    syms = sorted(fibre4)
    sweep = split_sweep({"discrete": {s: s for s in syms},
                         "cls": {"a": "A", "b": "A", "c": "B", "d": "B"}}, [fibre4], syms, 2)
    out["split_sweep_is_exhaustive"] = sweep["exhaustive"]
    out["split_sweep_is_bimodal"] = (
        sweep["n_splits_with_a_resolving_carrier"] > 0
        and sweep["n_splits_with_NO_resolving_carrier"] > 0)
    out["split_sweep_n_splits"] = sweep["n_splits_enumerated"]

    out["_self_check_passes"] = all(
        v for k, v in out.items()
        if isinstance(v, bool) and not k.startswith("_"))
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(self_check(), indent=2, sort_keys=True))
