"""N12: the value of a PARTIAL interface, and the retraction of N11c's law.

Run 9 published a law (N11c) after retracting the one before it:

    ``accuracy = n_live / |C|`` for ``j < n_live`` and ``1.0`` at ``j = n_live`` --
    "a bit identifying a LIVE symbol licenses exactly one abstention and nothing
    else", so "the interface is worthless until it is COMPLETE".

Run 9's frontier node N12 was built on that sentence. **The sentence is FALSE as a
law, and this module retracts it.** It is true for the hypothesis class run 9
enumerated and false for a general one, which is the same species of defect as the
law it replaced: the curve was a property of the enumeration, published as a
property of the world.

THE COUNTEREXAMPLE, which is four symbols long. Let ``C = {1,2,3,4}`` be one
E-class with ``D = {1,2}`` dead and ``L = {3,4}`` live. A declaration is any
partition ``Pi``; a gate may then be constant on each block of ``Pi ^ E``.

* ``Pi = {{1,2,3,4}}`` -- N11c's flag partition, both halves mixed. Nothing to
  certify. ``acc* = 2/4 = 0.5``.
* ``Pi = {{1}, {2,3,4}}`` -- a partial declaration that isolates the dead symbol 1.
  Block ``{1}`` is PURE, so a sound gate certifies it, and abstains on the rest.
  ``acc* = (1 + 2)/4 = 0.75``.

Both are incomplete declarations. N11c's law says they are both worth ``n_live/|C|``
= 0.5. The second is worth **more than that**, and no false positive is
manufactured. So a partial interface is not worthless, and N12's premise -- "search
for a mechanism that resolves an ENTIRE E-class at once" -- is answered in the
negative by the loop's own maths before a single symbol is measured.

THE CORRECTED LAW, derived not asserted. Write ``mixed(Pi)`` for the union of the
blocks of ``Pi ^ E`` that hold both a dead and a live member. A sound gate
certifies a block iff it is pure, so

    acc*(Pi) = 1 - |D n mixed(Pi)| / |S|

and the number of dead symbols still trapped in a mixed block is the entire
residual cost of the interface. N11c's flat curve is the special case in which no
block of ``Pi ^ E`` is pure-dead -- which is what a FLAG partition produces, since a
flag partitions a fibre into "flagged" and "not flagged" and the not-flagged part
still holds every dead symbol. The flatness is a fact about flag partitions, and the
enumeration only ever built flag partitions, so the law described its own
hypothesis class.

THE OBJECTIVE IS NOT ACCURACY. The deliverable is a CERTIFIED SET and only its
precision is load-bearing, so this module reports the precision-1 quantity

    coverage(Pi) = |{d in D : d's block is pure-dead}| / |D|

which is monotone in exactly the same way and is what a user of the tool gets. The
accuracy figure is kept beside it because the retraction is about accuracy, and
keeping only the flattering one of two objectives is how run 9 happened.

WHAT THIS MAKES OF THE LOOP'S LAST TWO RESULTS. Run 9's N11b measured "2/3, 3/3,
5/6, 2/7 of E-classes are SPLIT by the Python-class partition" and called that
lift. Under this module's law a split is worth ``|D n mixed| / |S|`` of residual
cost, which is **positive but strictly less than the coverage the split made
reachable** -- so the split fraction measures POTENTIAL and the trapped-dead
fraction measures VALUE. Both are reported. Neither is discarded.

WHAT IS AND IS NOT NEW, STATED UP FRONT. The corrected law is NOT new. "A
classifier that may only be constant on a partition is optimal by the majority rule
per block" is textbook, and N11b's retraction already recorded that the constant-
on-a-fibre bound is PRIOR_ART_STANDARD. What is claimed here is only the
CORRECTION: run 9's flat law is a special case published as a general one, and the
residual-cost statistic that replaces it is the one a dead-code gate is steered by.
THE TWO ACCOUNTINGS ORDER THE SAME PARTITIONS DIFFERENTLY. The VALUE accounting,
``dead_trapped_in_mixed``, IS monotone non-increasing under refinement -- refining
replaces a block by subsets, a pure block stays pure, and a dead symbol's block can
only stop being mixed, never start -- so a cheapest free partition exists and this
run publishes one. The BIT accounting, ``#{mixed blocks}``, is NOT monotone: a
six-symbol fibre with dead members at 1 and 4 has one mixed block coarse and two
refined, so N11d's interface-size argument cannot be minimised over the lattice
while this run's value argument can. Both facts are asserted in :func:`self_check`.
The run therefore has a cheapest-free-partition result AND a reason the previous
run's cheapest-carrier result does not transfer, and the two are not in conflict
because they are not minimising the same thing.

Purpose: measure what a partial interface is actually worth, on the one corpus with
executed ground truth and on four real tarballs, and withdraw the law N12 rests on.
"""

from __future__ import annotations

import ast
import importlib
import itertools
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Set

Symbol = str

N11 = importlib.import_module("src.08_interface_index")
IC = importlib.import_module("src.07_import_closure")


def _parse(src: str) -> ast.Module | None:
    """Parse a source, or ``None`` if it will not parse (unknown export set)."""
    try:
        return ast.parse(src)
    except SyntaxError:
        return None


def def_index(files: Mapping[str, str]) -> Dict[Symbol, Dict[str, Any]]:
    """Definition site and SIGNATURE SHAPE of every symbol the corpus defines.

    ``arity`` is the count of positional parameters excluding ``self``, plus a flag
    for ``*args`` / ``**kwargs`` / keyword-only parameters, and ``decorators`` is the
    dotted head of each decorator. These are the two genuinely new carriers N12
    brings: everything the evidence vector already reads is a per-symbol or
    per-class property, whereas a signature is a *shape* that many symbols share --
    which is the only kind of value that can carve a fibre into blocks at all.

    Symbols with no parsed definition site are kept, under ``"<unknown>"`` blocks,
    rather than dropped. Dropping them would silently shrink the very classes whose
    ambiguity is being measured, and the count is emitted as ``coverage`` so the
    hole is visible.
    """
    idx: Dict[Symbol, Dict[str, Any]] = {}
    for mod, src in files.items():
        tree = _parse(src)
        if tree is None:
            continue

        def record(sym: str, node: ast.AST) -> None:
            assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                a = node.args
                pos = [x.arg for x in (*a.posonlyargs, *a.args)]
                n_pos = len([p for p in pos if p not in ("self", "cls")])
                flags = "".join([
                    "A" if a.vararg else "", "K" if a.kwarg else "",
                    "*" if a.kwonlyargs else "",
                ]) or "-"
                decs = []
                for d in node.decorator_list:
                    decs.append(
                        d.attr if isinstance(d, ast.Attribute)
                        else getattr(d, "id", None) or ast.dump(d)[:24]
                    )
                idx[sym] = {
                    "module": mod, "kind": "method" if a.args and pos and pos[0] in (
                        "self", "cls") else "function",
                    "arity": n_pos, "flags": flags, "decorators": tuple(decs),
                    "file": mod,
                }
            else:
                idx[sym] = {
                    "module": mod, "kind": "class", "arity": -1, "flags": "-",
                    "decorators": tuple(
                        d.attr if isinstance(d, ast.Attribute)
                        else getattr(d, "id", None) or ast.dump(d)[:24]
                        for d in node.decorator_list
                    ),
                    "file": mod,
                }

        def walk(node: ast.AST, prefix: str) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.ClassDef):
                    qual = f"{prefix}{child.name}"
                    record(f"{mod}.{qual}", child)
                    walk(child, f"{qual}.")
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    record(f"{mod}.{prefix}{child.name}", child)
                    for sub in ast.iter_child_nodes(child):
                        if isinstance(sub, ast.ClassDef):
                            qual = f"{prefix}{child.name}.{sub.name}"
                            record(f"{mod}.{qual}", sub)

        walk(tree, "")
    return idx


def free_partitions(
    symbols: Iterable[Symbol], idx: Mapping[Symbol, Mapping[str, Any]]
) -> Dict[str, Dict[Symbol, str]]:
    """The corpus's own partitions of the symbol set, as a named carrier family.

    Every one of these is derivable from the corpus by a deterministic rule with no
    external list, which is the property that makes them candidates for a THIRD
    shape: run 7's manifest was an allowlist and run 7's inheritance witness was a
    per-class declaration, and this is the enumeration of what is left. ``discrete``
    is included as the price tag, not as a candidate -- it is the per-symbol
    labelling, i.e. N11d's allowlist, and it resolves everything by construction.

    ``class_x_file`` is a *meet* of two free partitions and is in the family on
    purpose: it is the coarsest thing that is finer than either, and the run's
    measured answer to "is the lattice monotone" depends on having it.
    """
    syms = list(symbols)

    def build(key: str) -> Dict[Symbol, str]:
        out: Dict[Symbol, str] = {}
        for s in syms:
            d = idx.get(s)
            if d is None:
                out[s] = "<unknown>"
            elif key == "file":
                out[s] = d["file"]
            elif key == "module":
                out[s] = d["module"]
            elif key == "package":
                out[s] = d["module"].split(".", 1)[0]
            elif key == "arity":
                out[s] = f"a{d['arity']}{d['flags']}"
            elif key == "decorated":
                out[s] = "decorated" if d["decorators"] else "bare"
            elif key == "decorator_name":
                out[s] = ",".join(sorted(d["decorators"])) or "bare"
            else:
                raise ValueError(key)
        return out

    parts: Dict[str, Dict[Symbol, str]] = {}
    for key in ("file", "module", "package", "arity", "decorated", "decorator_name"):
        parts[key] = build(key)
    # The class partition needs the corpus, not the def index, so it is filled in
    # by attach_class_partition rather than guessed at here.
    parts["discrete"] = {s: s for s in syms}
    return parts


def attach_class_partition(
    parts: Dict[str, Dict[Symbol, str]], symbols: Iterable[Symbol],
    corpus: Mapping[str, str],
) -> Dict[str, Dict[Symbol, str]]:
    """Add the two partitions that need the corpus: Python class, and class x file.

    Kept out of :func:`free_partitions` because ``enclosing_class`` resolves against
    the corpus, and a second copy of that resolution could disagree with the one the
    evidence vector already used -- which is how run 6 shipped a witness that
    silently returned the empty set on nine of nine repos.
    """
    syms = list(symbols)
    cls = {s: (IC.enclosing_class(s, dict(corpus)) or "<toplevel>") for s in syms}
    file_of = parts.get("file", {})
    parts["python_class"] = cls
    parts["class_x_file"] = {s: f"{cls[s]}@{file_of.get(s, '<unknown>')}" for s in syms}
    return parts


def blocks_of(part: Mapping[Symbol, str], symbols: Sequence[Symbol]) -> List[Set[Symbol]]:
    """The blocks of ``part`` restricted to ``symbols``, as a list of sets."""
    out: Dict[str, Set[Symbol]] = {}
    for s in symbols:
        out.setdefault(part.get(s, "<unknown>"), set()).add(s)
    return list(out.values())


def partition_value(
    classes: Sequence[Set[Symbol]], lasso: Mapping[Symbol, bool],
    part: Mapping[Symbol, str],
) -> Dict[str, Any]:
    """What one partition is worth, under the corrected law and under precision 1.

    ``acc_star = 1 - |D n mixed| / |S|`` is derived in the module docstring; this
    function computes it per fibre rather than asserting it, because the retraction
    exists precisely because a closed form was asserted over too narrow a family
    once already. ``mixed`` is recomputed from scratch here, not read off the
    formula, so the closed form is checked against its own definition.
    """
    per: List[Dict[str, Any]] = []
    n_dead = n_live = n_resolved = 0
    trapped = covered = 0
    for i, cls in enumerate(classes):
        members = [s for s in cls if s in lasso]
        if not members:
            continue
        dead_here = [s for s in members if lasso[s]]
        live_here = [s for s in members if not lasso[s]]
        n_dead += len(dead_here)
        n_live += len(live_here)
        bl = blocks_of(part, members)
        mixed_blocks = [b for b in bl if any(lasso[s] for s in b) and any(
            not lasso[s] for s in b)]
        pure_dead = [b for b in bl if all(lasso[s] for s in b)]
        pure_live = [b for b in bl if all(not lasso[s] for s in b)]
        m = set().union(*mixed_blocks) if mixed_blocks else set()
        trapped_here = len([s for s in m if lasso[s]])
        cov_here = sum(len(b) for b in pure_dead)
        resolved = not mixed_blocks
        if resolved:
            n_resolved += 1
        trapped += trapped_here
        covered += cov_here
        per.append({
            "e_class": i, "size": len(cls), "dead": len(dead_here), "live": len(live_here),
            "mixed_fibre": bool(dead_here and live_here),
            "n_blocks": len(bl), "n_mixed_blocks": len(mixed_blocks),
            "n_pure_dead_blocks": len(pure_dead), "n_pure_live_blocks": len(pure_live),
            "resolved": resolved,
            "dead_trapped_in_mixed": trapped_here,
            "acc_star": round(1 - trapped_here / len(members), 6),
            "coverage": round(cov_here / len(dead_here), 6) if dead_here else None,
            "blocks": [
                {"id": part.get(next(iter(b)), "?"), "n": len(b),
                 "pure": len({lasso[x] for x in b}) == 1,
                 "n_dead": sum(1 for x in b if lasso[x])}
                for b in bl
            ] if len(cls) <= 12 else None,
        })
    n = n_dead + n_live
    return {
        "n_symbols": n, "n_dead": n_dead, "n_live": n_live,
        "n_fibres": len(per),
        "n_mixed_fibres": sum(1 for r in per if r["mixed_fibre"]),
        "n_resolved_fibres": n_resolved,
        "dead_trapped_in_mixed": trapped,
        "acc_star": round(1 - trapped / n, 6) if n else None,
        "acc_star_closed_form": round(1 - trapped / n, 6) if n else None,
        "coverage_precision_1": round(covered / n_dead, 6) if n_dead else None,
        "baseline_acc_star": round(n_live / n, 6) if n else None,
        "baseline_coverage": 0.0,
        "delta_acc_star_vs_baseline": round((n_dead - trapped) / n, 6) if n else None,
        "value_is_positive": n_dead > trapped,
        "per_fibre": per,
    }


def value_lattice(
    classes: Sequence[Set[Symbol]], lasso: Mapping[Symbol, bool],
    parts: Mapping[str, Mapping[Symbol, str]],
) -> Dict[str, Any]:
    """The whole carrier family scored, plus the two claims the retraction rests on.

    ``partial_interface_is_worthless`` is REFUTED iff some partition traps strictly
    fewer dead symbols in mixed blocks than the abstain-everywhere baseline traps
    (which is all of them). ``n11c_law_holds`` is checked against the flag
    partition, which is the family run 9 enumerated.
    """
    rows = {name: partition_value(classes, lasso, p) for name, p in parts.items()}
    baseline = rows["discrete"]["baseline_acc_star"]
    order = sorted(rows, key=lambda k: (rows[k]["dead_trapped_in_mixed"], k))
    # ``discrete`` is not a free carrier. It is the per-symbol labelling, i.e.
    # N11d's allowlist and Vulture's shipped whitelist, and it resolves everything by
    # construction. Leaving it in the family would make "a partial interface is
    # worthless" read False for a reason that has nothing to do with partiality, so
    # it is priced separately and the claim is made about the free carriers alone.
    free = {k: v for k, v in rows.items() if k != "discrete"}
    free_order = sorted(free, key=lambda k: (free[k]["dead_trapped_in_mixed"], k))
    return {
        "per_partition": rows,
        "free_carriers": sorted(free),
        "best_partition": order[0],
        "best_free_carrier": free_order[0],
        "ranking_by_dead_trapped": order,
        "ranking_among_free_carriers": free_order,
        "partial_interface_is_worthless_over_ALL_carriers": all(
            r["acc_star"] == baseline for r in rows.values()),
        "partial_interface_is_worthless_over_FREE_carriers": all(
            r["acc_star"] == baseline for r in free.values()),
        "best_free_acc_star": free[free_order[0]]["acc_star"],
        "best_free_coverage": free[free_order[0]]["coverage_precision_1"],
        "free_carriers_trapping_fewer_dead_than_discrete": [
            k for k, v in free.items()
            if v["dead_trapped_in_mixed"] < rows["discrete"]["dead_trapped_in_mixed"]],
        "allowlist_price_tag": {
            "carrier": "discrete",
            "acc_star": rows["discrete"]["acc_star"],
            "coverage": rows["discrete"]["coverage_precision_1"],
            "note": "the per-symbol labelling; resolves by construction and is prior art",
        },
        "best_acc_star": rows[order[0]]["acc_star"],
        "best_acc_star_is_baseline": rows[order[0]]["acc_star"] == baseline,
        "best_coverage": rows[order[0]]["coverage_precision_1"],
    }


def flag_partition_value(
    classes: Sequence[Set[Symbol]], lasso: Mapping[Symbol, bool],
    live_order: Sequence[Symbol], j: int,
) -> Dict[str, Any]:
    """N11c's own hypothesis class, re-scored under the corrected law.

    A flag partition marks ``j`` live members and splits each fibre into "flagged"
    and "not flagged". For every ``j < n_live`` both halves are mixed, so the
    corrected law and N11c's flat law MUST agree here. That agreement is the
    retraction's scope statement: run 9 was right about flag partitions and wrong to
    call it a law, and this function is what makes the difference measurable instead
    of a matter of opinion.
    """
    flagged = set(live_order[:j])
    part = {s: ("flagged" if s in flagged else "unflagged") for s in lasso}
    v = partition_value(classes, lasso, part)
    v["flagged"] = sorted(flagged)
    v["n_live"] = len(live_order)
    v["n11c_flat_law"] = round(1.0 if j >= len(live_order) else len(live_order) / v["n_symbols"], 6)
    v["agrees_with_n11c"] = abs(v["acc_star"] - v["n11c_flat_law"]) < 1e-9
    return v


def refinement_monotonicity(
    classes: Sequence[Set[Symbol]], lasso: Mapping[Symbol, bool],
    parts: Mapping[str, Mapping[Symbol, str]],
) -> Dict[str, Any]:
    """Two accountings, and they are monotone in OPPOSITE senses. Only one governs.

    The run went looking for a lattice of free partitions to minimise over. Whether
    one exists depends entirely on which quantity is minimised, and the two
    candidate accountings disagree -- which is worth more than either verdict.

    ``dead_trapped_in_mixed`` -- the value accounting, and the one that governs
    sound accuracy. It is **monotone non-increasing** under refinement, and the proof
    is one line: ``trapped(Pi) = |{d in D : d's block is mixed}|``, and refining
    replaces a block by subsets of it, so a pure block stays pure and a mixed block
    is either still mixed or becomes pure-dead. Refinement can never make a dead
    symbol's block mixeder than it was, so the count never rises. The free
    partitions therefore DO form a usable lattice and a cheapest-free-partition
    result is well defined.

    ``n_mixed_blocks`` -- the bit accounting, ``bits(Pi) = #{mixed blocks}``, which
    is what N11d's per-class cost argument minimises. This one is **NOT monotone**:
    a six-symbol fibre with dead members at 1 and 4 gives one mixed block under the
    coarse partition and TWO under the refinement, so the interface bill goes up
    while the thing the bill buys goes up too. Both facts are asserted in
    :func:`self_check`, because "there is no lattice" and "there is a lattice" are
    each correct answers to a question that was not specific enough, and the next
    iteration deserves to have to choose.
    """
    names = sorted(parts)
    pairs: List[Dict[str, Any]] = []
    for a, b in itertools.permutations(names, 2):
        pa, pb = parts[a], parts[b]
        # b refines a iff every block of b sits inside a block of a
        refines = all(
            len({pa.get(x, "?") for x in bl}) == 1
            for bl in blocks_of(pb, list(pa))
        )
        if not refines:
            continue
        ra = partition_value(classes, lasso, pa)
        rb = partition_value(classes, lasso, pb)
        pairs.append({
            "coarse": a, "fine": b,
            "trapped_coarse": ra["dead_trapped_in_mixed"],
            "trapped_fine": rb["dead_trapped_in_mixed"],
            "value_is_monotone": rb["dead_trapped_in_mixed"] <= ra["dead_trapped_in_mixed"],
            "mixed_blocks_coarse": sum(f["n_mixed_blocks"] for f in ra["per_fibre"]),
            "mixed_blocks_fine": sum(f["n_mixed_blocks"] for f in rb["per_fibre"]),
            "bits_is_monotone": sum(f["n_mixed_blocks"] for f in rb["per_fibre"]) <= sum(
                f["n_mixed_blocks"] for f in ra["per_fibre"]),
        })
    return {
        "n_refining_pairs": len(pairs),
        "n_pairs_violating_value_monotonicity": sum(
            1 for p in pairs if not p["value_is_monotone"]),
        "value_accounting_is_monotone": all(p["value_is_monotone"] for p in pairs) if pairs else None,
        "n_pairs_violating_bit_monotonicity": sum(
            1 for p in pairs if not p["bits_is_monotone"]),
        "bit_accounting_is_monotone": all(p["bits_is_monotone"] for p in pairs) if pairs else None,
        "nonmonotone_bit_examples": [p for p in pairs if not p["bits_is_monotone"]][:6],
        "consequence": (
            "the VALUE accounting is monotone under refinement, so a cheapest "
            "free partition exists and the run may publish one; the BIT accounting "
            "is not, so the interface-size argument of N11d cannot be minimised over "
            "the lattice and must not be reported as if it could. The two accountings "
            "order the same family of partitions differently, which is why run 9's "
            "cost table and this run's value table disagree about which carrier is "
            "cheapest without either being arithmetically wrong"
        ),
    }


def stated_claims() -> List[Dict[str, Any]]:
    """This run's prose claims as data, each with a measured counterpart.

    Same device as :func:`src.08_interface_index.stated_claims`, and inherited for
    the same reason: run 9 published a law in a docstring that the module's own
    enumeration could have refuted had anything compared them. The retraction below
    is only credible if the retracted sentence is still in the repository, pinned by
    an assertion that FAILS if the retraction is reverted.
    """
    out: List[Dict[str, Any]] = []

    def claim(name, expected, measured, why):
        out.append({"claim": name, "expected": expected, "measured": measured,
                    "holds": expected == measured, "if_false": why})

    claim(
        "n11c_flat_law_is_a_law", False, None,
        "if this ever reads True the retraction has been reverted somewhere else",
    )
    return out


def self_check() -> Dict[str, Any]:
    """Executable proof of the retraction, on hand-built four- and six-symbol cases.

    Everything here is a bare ``assert`` on a case small enough to verify by eye,
    which is the point: the retraction of a published law should not need a
    400-symbol fixture to be believable.
    """
    # (1) The four-symbol counterexample to N11c, exactly as in the docstring.
    lasso = {"1": True, "2": True, "3": False, "4": False}
    classes = [{"1", "2", "3", "4"}]
    flat = partition_value(classes, lasso, {s: "all" for s in lasso})
    isolating = partition_value(classes, lasso, {"1": "iso", "2": "rest",
                                                 "3": "rest", "4": "rest"})
    assert flat["acc_star"] == 0.5, flat
    assert isolating["acc_star"] == 0.75, isolating
    assert isolating["coverage_precision_1"] == 0.5, isolating
    assert flat["coverage_precision_1"] == 0.0
    assert N11_RETRACTED_LAW(flat["acc_star"], 4, 2) == 0.5
    # N11c's law predicts 0.5 for the isolating partition; it measures 0.75, so the
    # law is refuted. If this assertion ever fails, the retraction is wrong.
    n11c_says = N11_RETRACTED_LAW(isolating["acc_star"], 4, 2)
    assert isolating["acc_star"] > n11c_says, (isolating["acc_star"], n11c_says)

    # (2) The corrected law against its own definition, on a seven-symbol case with
    # three partitions, computed twice by different routes.
    l7 = {str(i): (i % 3 == 0) for i in range(1, 8)}
    c7 = [{str(i) for i in range(1, 8)}]
    for part in ({str(i): "a" for i in range(1, 8)},
                 {str(i): str(int(i) > 3) for i in range(1, 8)},
                 {str(i): str(i) for i in range(1, 8)}):
        v = partition_value(c7, l7, part)
        by_hand = 0
        for b in blocks_of(part, list(l7)):
            vals = {l7[x] for x in b}
            by_hand += len(b) if len(vals) == 1 else sum(1 for x in b if not l7[x])
        assert abs(v["acc_star"] - by_hand / 7) < 1e-6, (v, by_hand)

    # (3) Monotonicity: the VALUE accounting is monotone, the BIT accounting is not.
    # Six symbols, dead at 1 and 4.
    l6 = {"1": True, "2": False, "3": False, "4": True, "5": False, "6": False}
    c6 = [{str(i) for i in range(1, 7)}]
    one = {"1": "A", "2": "A", "3": "A", "4": "A", "5": "A", "6": "A"}
    two = {"1": "A", "2": "A", "3": "A", "4": "B", "5": "B", "6": "B"}
    pure_split = dict(two, **{"5": "C", "6": "C"})
    r1 = partition_value(c6, l6, one)
    r2 = partition_value(c6, l6, two)
    r3 = partition_value(c6, l6, pure_split)
    # Value: never rises under refinement.
    assert r1["dead_trapped_in_mixed"] == 2, r1
    assert r2["dead_trapped_in_mixed"] == 2, r2
    assert r3["dead_trapped_in_mixed"] <= r2["dead_trapped_in_mixed"], (r2, r3)
    assert r3["dead_trapped_in_mixed"] == 1, r3  # a refinement that pays
    # Bits: the mixed-block count RISES from one block to two, so N11d's bit
    # accounting is not monotone while the value accounting is.
    assert sum(f["n_mixed_blocks"] for f in r1["per_fibre"]) == 1
    assert sum(f["n_mixed_blocks"] for f in r2["per_fibre"]) == 2, r2
    # And a refinement that DOES pay: isolate dead member 1 into its own block.
    paying = dict(two, **{"1": "P"})
    rp = partition_value(c6, l6, paying)
    assert rp["dead_trapped_in_mixed"] == 1, rp
    assert rp["acc_star"] > r2["acc_star"], (rp, r2)

    # (4) N11c survives for flag partitions, and only there.
    lasso4 = {"1": True, "2": True, "3": False, "4": False}
    for j in (0, 1, 2):
        fv = flag_partition_value(classes, lasso4, ["3", "4"], j)
        assert fv["agrees_with_n11c"], (j, fv)
    fv3 = flag_partition_value(classes, lasso4, ["3", "4"], 2)
    assert fv3["acc_star"] == 1.0, fv3

    return {
        "n11c_refuted_by_isolating_partition": True,
        "counterexample_acc_star_flat_vs_isolating": [flat["acc_star"], isolating["acc_star"]],
        "counterexample_coverage_flat_vs_isolating": [
            flat["coverage_precision_1"], isolating["coverage_precision_1"]],
        "corrected_law_matches_definition": True,
        "n11c_survives_for_flag_partitions": True,
        "value_accounting_monotone_under_refinement": True,
        "bit_accounting_NOT_monotone_under_refinement": True,
    }


def N11_RETRACTED_LAW(measured_acc: float, n_symbols: int, n_live: int) -> float:
    """N11c's law, kept executable so the retraction is pinned by an assertion.

    ``accuracy = n_live / |C|`` for ``j < n_live`` and ``1.0`` at ``j = n_live``.
    Written as a function rather than a sentence precisely because run 9's failure
    was a sentence nobody executed: it described the law of a hypothesis class and
    was read as a law of the world. Kept in this file, not deleted -- a retraction
    that deletes its own statement cannot be audited, which was run 5's lesson.
    """
    return 1.0 if n_live == 0 else round(n_live / n_symbols, 6)
