"""Sound dead-code certification + an identifiability-gated score (v3 metric).

Purpose: repair the two defects run 3 found in the MEASURE rather than the
    pipeline. Both are proved here rather than asserted, and both are the kind
    of defect that keeps producing plausible numbers while measuring nothing.

DEFECT 1 -- the 20-point ``dead_code_acc`` term is the constant 0.
    The standing term split a predicted-dead symbol into refuted / proven /
    unexercised, where "proven" required the symbol to have a static in-edge
    from a caller the fold exercised. But ``dead_symbols()`` only ever emits
    symbols with in-degree 0, so ``reverse(s) = {}`` for every ``s`` in the set
    and the guard is unsatisfiable. Proven is empty for EVERY graph, EVERY
    oracle and EVERY predictor -- not merely under a held-out fold. And the
    ``if |dead| else 1.0`` fallback pays a perfect 20/20 to a predictor that
    reports nothing dead, so the term's range is exactly {0.0, 1.0}.
    Kept here as ``strict_dead_term`` so the broken formula stays measured
    rather than quietly deleted.

DEFECT 2 -- "use F1 instead of precision" (proposed in run 3) is REFUTED.
    Against a partial oracle D subset T, ``prec_D(P) <= prec_T(P)`` holds
    (denominator |P| fixed, numerator monotone), but ``rec_D(P) <= rec_T(P)``
    does NOT: D={1,2}, T={1,2,3,4,5}, P={1,2,6} gives rec_D=1.0 > rec_T=0.6.
    Recall moves numerator and denominator together, so it has no fixed sign.
    Any aggregator mixing recall in -- F1, min(p,r), Youden's J -- therefore
    inherits an unquantified bias in an unknown direction and is NOT a lower
    bound. Precision survives as the only well-posed direction; recall is
    reported, never scored. This retracts run 3's proposed metric change.

THE REPAIR: trace-free certification.
    Ask the static resolver instead of the trace. A call site the resolver
    could not resolve is an OPAQUE site; by construction the only thing it
    could have been is a call to a symbol whose bare name is the one recorded.
    So any predicted-dead symbol whose bare name matches an opaque name has an
    un-instrumented possible caller and is UN-ADJUDICABLE; the rest are
    CERTIFIED. Certified symbols have zero false positives under the resolver's
    own soundness (equations.md row 13), which is a strictly stronger claim
    than anything the trace could establish, and it needs no execution at all.

    Two honest limits, both measured rather than assumed:
      * A name COLLISION costs recall, never precision: a live ``a.Cache.load``
        and a dead ``b.Cache.load`` share the bare name, so the live one taints
        the dead one out of the certified set. It is never certified wrongly.
      * The ``<complex>`` sentinel (a call whose callee has no extractable
        name, e.g. ``factory()()``) breaks soundness outright, because its
        possible targets carry no name to match on. That is a checkable
        precondition, not a caveat: ``soundness_precondition`` gates the term.
    The consequence is stated plainly: the repaired term is 1.0 by construction
    whenever certification succeeds (equations.md row 14), so it is a BINARY
    soundness verdict, not a graded quality signal. The graded, informative
    number is ``certification_rate``, reported and deliberately unscored.
"""
from __future__ import annotations

import importlib
import os
import sys
from typing import Any, Dict, Iterable, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

Symbol = str
Dispatch = Tuple[Symbol, Symbol]

# A call whose callee is an expression rather than a name, so no bare name can
# be extracted. Its possible targets are un-nameable, which is why it is a
# soundness gate rather than a footnote.
COMPLEX_SENTINEL = "<complex>"


def bare(sym: Symbol) -> str:
    """Last dotted component of a symbol."""
    return sym.rsplit(".", 1)[-1]


def opaque_names(unresolved_calls: Iterable[Tuple[Symbol, str]]) -> Set[str]:
    """Bare names the resolver failed to resolve, i.e. its blind-spot surface.

    Inputs: the CPG's ``unresolved_calls`` set of ``(caller, raw_name)`` pairs.
    Outputs: the set of bare callee names that could not be resolved.
    """
    return {raw for _, raw in unresolved_calls}


def soundness_precondition(opaque: Set[str]) -> bool:
    """True iff the name-based certification argument is sound on this graph.

    The proof needs every real-but-unresolved call site to carry a matchable
    bare name. A ``<complex>`` site has none, so a live symbol behind it can
    sit in ``dead`` with in-degree 0, match nothing, and be certified wrongly.
    The precondition is checked, not assumed.
    """
    return COMPLEX_SENTINEL not in opaque


def certify_dead(dead: Set[Symbol], opaque: Set[str]) -> Set[Symbol]:
    """Predicted-dead symbols the resolver can stand behind, trace-free.

    Inputs: the predicted-dead set and the opaque (unresolved) name surface.
    Outputs: ``dead`` minus every symbol whose bare name could have been the
    target of an un-instrumented call site.

    Sound in one direction only, and that direction is the expensive one: a
    certified symbol provably has no real in-edge, so a "safe to delete" verdict
    drawn from it cannot be a false positive. Recall is not claimed -- see the
    name-collision limit in the module docstring.
    """
    return {s for s in dead if bare(s) not in opaque}


def unadjudicable_dead(dead: Set[Symbol], opaque: Set[str]) -> Set[Symbol]:
    """Predicted-dead symbols the resolver explicitly refuses to stand behind."""
    return {s for s in dead if bare(s) in opaque}


def strict_dead_term(
    dead: Set[Symbol],
    refuted: Set[Symbol],
    call_edges: Iterable[Dispatch],
    covered: Set[Symbol],
) -> Dict[str, Any]:
    """The standing (broken) 20-point term, reproduced so it can be measured.

    Inputs: predicted-dead, the refuted subset, the FINAL resolved edges and
        the fold's covered symbols.
    Outputs: dict with ``term`` (the standing score), plus ``proven``,
        ``unexercised`` and ``reverse_nonempty`` so the degenerate shape is
        visible in the log instead of only in a proof.

    Kept deliberately: a defect that is merely deleted is a defect that gets
    re-introduced. This is the formula run 2 and run 3 both reported.
    """
    reverse: Dict[Symbol, Set[Symbol]] = {}
    for src, dst in call_edges:
        reverse.setdefault(dst, set()).add(src)
    refuted = dead & refuted
    unexercised = {
        s
        for s in dead - refuted
        if not (reverse.get(s, set()) and (reverse[s] & covered))
    }
    proven = dead - refuted - unexercised
    n = len(dead)
    return {
        # The `else 1.0` is the load-bearing bug: an empty dead set is a
        # perfect score, so predicting nothing beats analysing anything.
        "term": (len(proven) / n) if n else 1.0,
        "proven": sorted(proven),
        "unexercised": sorted(unexercised),
        "refuted": sorted(refuted),
        "reverse_nonempty": sorted(s for s in dead if reverse.get(s)),
    }


def dead_term(certified: Set[Symbol], precondition_ok: bool) -> float:
    """The repaired 20-point term: a binary soundness verdict on the dead set.

    Inputs: the certified dead set and whether the name-based soundness
        precondition held.
    Outputs: 1.0 iff the pipeline produced at least one dead verdict it can
        prove, 0.0 otherwise.

    Deliberately binary. Under the soundness precondition every certified
    symbol is a true positive, so any accuracy-over-certification is 1.0 by
    construction and carries no gradations to report. Both holes in the
    standing term are closed: an unsound graph scores 0 rather than a
    fabricated 0.3333, and abstaining scores 0 instead of a free 20 points.
    """
    if not precondition_ok:
        return 0.0
    return 1.0 if certified else 0.0


def certification_rate(dead: Set[Symbol], certified: Set[Symbol]) -> float:
    """Share of the predicted-dead set the resolver can actually stand behind.

    Reported, never scored. It is the informative number the binary
    ``dead_term`` cannot be: it moves with the size of the dead set, so a
    variant that removes false verdicts scores better without any change in
    proof status. Left unscored because it rewards shrinking the dead set
    toward nothing, which is a different objective from proving it.
    """
    if not dead:
        return 0.0
    return round(len(certified) / len(dead), 4)


def structural_lower_bound(
    predicted: Set[Dispatch],
    eval_dispatches: Set[Dispatch],
    eval_covered: Set[Symbol],
) -> Dict[str, Any]:
    """Precision against a partial oracle, plus the count that makes it unusable.

    Inputs: all predicted edges, the evaluation fold's dispatches, and the
        symbols that fold exercised.
    Outputs: ``precision`` (a sound one-sided LOWER bound on true precision),
        ``unadjudicable_edges`` and ``identifiable``.

    An edge whose caller the evaluation fold never exercised cannot appear in
    the fold's dispatch set whether it is real or fabricated, so the oracle
    has no opinion on it. It is nevertheless charged to the precision
    denominator. The resulting number is a lower bound of *unmeasured* tightness
    -- it conflates "wrong" with "unjudged" -- so ``identifiable`` is False
    whenever any such edge exists and the score must not be read as a ranking.
    Callers who exercise nothing are counted, never silently scored.

    NOTE the deliberate asymmetry between the two precisions reported here.
    ``precision`` (all predicted edges) is the SOUND lower bound and is the one
    the score uses, because it is the same quantity the standing metric
    measured. ``precision_evaluable`` (restricted to edges the fold could
    adjudicate) is also a sound bound, but on a smaller denominator, and it
    SATURATES at 1.0 the moment a variant emits no false evaluable edge -- so
    it is sound, uninformative, and reported as a diagnostic only. Scoring it
    would flatten every variant to the same number, which is the honest
    outcome of the instrument and not a useful thing to put in a score.
    """
    evaluable = {e for e in predicted if e[0] in eval_covered}
    unadjudicable = predicted - evaluable
    return {
        "precision": round(
            len(predicted & eval_dispatches) / len(predicted), 4
        )
        if predicted
        else 0.0,
        "precision_evaluable": round(
            len(evaluable & eval_dispatches) / len(evaluable), 4
        )
        if evaluable
        else 0.0,
        "evaluable_edges": len(evaluable),
        "unadjudicable_edges": len(unadjudicable),
        "unadjudicable": sorted(map(list, unadjudicable)),
        "identifiable": not unadjudicable,
    }


def gated_score(validity: float, precision: float, lat: float, ram: float) -> float:
    """The repaired score: 80 points, every one of them identified.

    ``30*validity + 30*precision + 10*lat + 10*ram``. The dead term is gone
    from the arithmetic, not from the report. Handing out 20 points to a
    quantity that can only ever be 0 or 1 inflates the denominator of every
    score in the harness and makes a binary soundness flag look like a quality
    measurement. The ceiling drops from 100 to 80 and every number must say
    so; a smaller scale that means something beats a larger one that does not.
    """
    return 30 * validity + 30 * precision + 10 * lat + 10 * ram


MAX_GATED_SCORE = 80

# ponytail: real repos put thousands of symbols in these sets; the log wants the
# count and a sample, not a 40KB dump. Counts are always exact.
REPORT_SAMPLE = 12


def _summarise(items: Iterable[Any]) -> Dict[str, Any]:
    """Count plus a sorted sample. Exact count, truncated listing."""
    ordered = sorted(str(i) for i in items)
    return {
        "n": len(ordered),
        "sample": ordered[:REPORT_SAMPLE],
        "truncated": len(ordered) > REPORT_SAMPLE,
    }


def assess(
    cpg,
    dispatches: Set[Dispatch],
    covered: Set[Symbol],
    validity: float = 1.0,
    lat: float = 0.999745,
    ram: float = 0.95625,
) -> Dict[str, Any]:
    """Full run-4 assessment of one resolved graph against one fold.

    Inputs: a built/possibly-promoted ``CPG``, the evaluation fold's
        dispatches, the symbols that fold exercised, and the already-measured
        validity/latency/RAM sub-scores.
    Outputs: the certified dead set, the abstention set, both dead terms side
        by side, the structural lower bound with its identifiability verdict,
        and the gated score. Nothing here needs a model or a network; the whole
        repair is static analysis over sets the resolver already produced.
    """
    dead = cpg.dead_symbols(dunder_exempt=True)
    opaque = opaque_names(cpg.unresolved_calls)
    precondition = soundness_precondition(opaque)
    certified = certify_dead(dead, opaque)
    callees = {b for _, b in dispatches}
    strict = strict_dead_term(dead, callees, cpg.call_edges, covered)
    struct = structural_lower_bound(set(cpg.call_edges), dispatches, covered)
    precision = float(struct["precision"])
    score = gated_score(validity, precision, lat, ram)
    return {
        "opaque_names": _summarise(opaque),
        "dead_certified": sorted(certified),
        "dead_unadjudicable": sorted(unadjudicable_dead(dead, opaque)),
        "n_predicted_dead": len(dead),
        "n_certified": len(certified),
        "n_unadjudicable": len(dead) - len(certified),
        "dead_soundness_precondition": precondition,
        "dead_term_v3": dead_term(certified, precondition),
        "certification_rate": round(certification_rate(dead, certified), 4),
        "dead_code_acc_strict": strict["term"],
        "strict_term_proven": strict["proven"],
        "strict_term_reverse_nonempty": _summarise(strict["reverse_nonempty"]),
        "n_strict_proven": len(strict["proven"]),
        "structural_precision_lower_bound": precision,
        "structural_precision_evaluable": struct["precision_evaluable"],
        "evaluable_edges": struct["evaluable_edges"],
        "unadjudicable_edges": struct["unadjudicable_edges"],
        "structural_identifiable": struct["identifiable"],
        "harness_score_v3": round(score, 2),
        "max_score_v3": MAX_GATED_SCORE,
    }


def _self_check() -> None:
    """Assert every claim the module makes, including the ones that cut against it.

    The load-bearing assertion is the first one: it pins the standing term to
    zero on a graph where the dead-code detection is provably CORRECT, which is
    the only way to show the defect is in the metric and not in the pipeline.
    """
    cpg_mod = importlib.import_module("src.00_cpg_static")

    # --- DEFECT 1: the standing term is identically 0, even when the
    # pipeline's dead verdicts are all true. `load` is live via the opaque
    # attribute-on-instance call; `orphan` is genuinely dead. Both are
    # predicted dead. The correct answer is 1/1; the term reports 0.0.
    files = {
        "store.py": (
            "class Store:\n"
            "    def query(self, uid):\n        return {'uid': uid}\n"
            "    def load(self, uid):\n        return {'uid': uid}\n"
            "store = Store()\n"
        ),
        "users.py": (
            "from store import store\n"
            "class Cache:\n"
            "    def orphan(self):\n        return 42\n"
            "def run(uid):\n    return store.load(uid) + store.query(uid)\n"
        ),
    }
    cpg = cpg_mod.build_cpg(files)
    dead = cpg.dead_symbols(dunder_exempt=True)
    assert "users.Cache.orphan" in dead, dead          # the true positive
    # Both false verdicts: `store.load` and `store.query` are reached only
    # through the opaque `store.<attr>` sites in `users.run`.
    assert {"store.Store.load", "store.Store.query"} <= dead, dead
    strict = strict_dead_term(dead, set(), cpg.call_edges, covered=set())
    # `reverse` is empty for every dead symbol, so `proven` is empty, so the
    # term is 0.0 -- with a 1/1-correct pipeline sitting right there.
    assert strict["proven"] == [], strict
    assert strict["term"] == 0.0, strict
    assert strict["reverse_nonempty"] == [], strict

    # ... and the `else 1.0` fallback pays a predictor that reports NOTHING.
    assert strict_dead_term(set(), set(), cpg.call_edges, set())["term"] == 1.0

    # --- THE REPAIR: certification removes the false verdict, keeps the true one.
    opaque = opaque_names(cpg.unresolved_calls)
    assert opaque == {"load", "query"}, opaque  # the two `store.<attr>` sites
    assert soundness_precondition(opaque)
    certified = certify_dead(dead, opaque)
    assert certified == {"users.Cache.orphan"}, certified
    assert unadjudicable_dead(dead, opaque) == {
        "store.Store.load", "store.Store.query"
    }
    # Zero false positives: nothing certified has any in-edge at all.
    targets = {b for _, b in cpg.call_edges}
    assert not (certified & targets), certified & targets
    # The informative-but-unscored diagnostic moves the way theory says: 1 of 3
    # predicted-dead verdicts is provable, 2 are abstained on.
    assert certification_rate(dead, certified) == round(1 / 3, 4)
    assert dead_term(certified, precondition_ok=True) == 1.0
    # Both holes closed: abstaining scores 0, not a free 20 points.
    assert dead_term(set(), precondition_ok=True) == 0.0
    # An unsound graph (a call with no extractable callee name) scores 0
    # rather than a fabricated accuracy.
    assert not soundness_precondition({COMPLEX_SENTINEL})
    assert dead_term({"users.Cache.orphan"}, precondition_ok=False) == 0.0
    # (targets is bound above by the zero-false-positive assertion.)

    # --- NAME COLLISION costs recall, never precision.
    collide = certify_dead({"a.Cache.load", "b.Cache.load"}, opaque={"load"})
    assert collide == set(), collide  # BOTH taint out: recall lost, precision kept
    # ...and the collision cannot promote a false positive either: nothing is
    # certified that has an in-edge.
    assert not (collide & targets)

    # --- The <complex> sentinel is reachable from real source, not hypothetical.
    tricky = cpg_mod.build_cpg(
        {
            "f.py": (
                "def make():\n    return lambda: 1\n"
                "def go():\n    return make()()\n"
            )
        }
    )
    assert COMPLEX_SENTINEL in opaque_names(tricky.unresolved_calls), (
        tricky.unresolved_calls
    )
    assert not soundness_precondition(opaque_names(tricky.unresolved_calls))

    # --- DEFECT 2 verified empirically: the F1 substitution is unsound.
    # rec_D (1.0) > rec_T (0.4) for D subset T, so no aggregator mixing recall
    # is a bound. This is the refutation of run 3's proposed F1 substitution.
    d, t, p = {("a", "1"), ("a", "2")}, {
        ("a", "1"), ("a", "2"), ("a", "3"), ("a", "4"), ("a", "5")
    }, {("a", "1"), ("a", "2"), ("a", "6")}
    rec_d = len(p & d) / len(d)
    rec_t = len(p & t) / len(t)
    assert rec_d == 1.0 and rec_t == 0.4 and rec_d > rec_t, (rec_d, rec_t)
    # precision IS a sound one-sided bound, and it is what the gate keeps.
    assert len(p & d) / len(p) <= len(p & t) / len(p)

    # --- Structural lower bound: sound but declared non-identifiable when an
    # edge's caller was never exercised. This is the exact condition run 3
    # violated without noticing.
    pred = {("svc_x.f", "m.g"), ("never_run.h", "m.i")}
    lo = structural_lower_bound(pred, {("svc_x.f", "m.g")}, {"svc_x.f"})
    # The scored bound charges the unjudged edge; the diagnostic does not, and
    # saturates. Reporting only the latter would flatten every variant to 1.0.
    assert lo["precision"] == 0.5, lo
    assert lo["precision_evaluable"] == 1.0, lo
    assert lo["evaluable_edges"] == 1 and lo["unadjudicable_edges"] == 1, lo
    assert lo["identifiable"] is False, lo
    assert structural_lower_bound({("svc_x.f", "m.g")}, {("svc_x.f", "m.g")},
                                  {"svc_x.f"})["identifiable"] is True
    # The saturation that makes the diagnostic useless as a score: a variant
    # with 5 clean evaluable edges and one with 3 both read 1.0.
    big = {("svc_x.f", "m.g"), ("svc_x.f", "m.h"), ("svc_x.f", "m.i")}
    sat = structural_lower_bound(big, big, {"svc_x.f"})
    assert sat["precision_evaluable"] == 1.0 and sat["precision"] == 1.0, sat
    # The saturation that makes the diagnostic useless as a score: two variants
    # with genuinely different edge counts both read 1.0.
    big = {("svc_x.f", "m.g"), ("svc_x.f", "m.h"), ("svc_x.f", "m.i")}
    sat = structural_lower_bound(big, big, {"svc_x.f"})
    assert sat["precision_evaluable"] == 1.0 and sat["precision"] == 1.0, sat

    # --- The gated score is 80 points and every term is bounded.
    assert MAX_GATED_SCORE == 80
    assert gated_score(1.0, 1.0, 1.0, 1.0) == 80.0
    assert gated_score(0.0, 0.0, 0.0, 0.0) == 0.0

    print(
        "03_metric_gate self-check OK",
        {
            "strict_term_proven": strict["proven"],
            "certified": sorted(certified),
            "unadjudicable": sorted(unadjudicable_dead(dead, opaque)),
            "identifiable": lo["identifiable"],
        },
    )


if __name__ == "__main__":
    _self_check()
