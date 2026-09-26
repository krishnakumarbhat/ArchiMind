"""Trace-informed edge promotion for the static CPG (variation v3).

Purpose: recover the call edges that the conservative static resolver refuses
    to guess. The dominant blind spot is the attribute-on-instance call
    (``self.s.query(uid)``), which is invisible without a points-to set, and it
    is the *single* root cause behind the run-2 weaknesses (``recall 0.5``,
    ``cpg_resolution_rate 0.5``, ``dead_code_acc 0.3333``).

Inputs: a built ``CPG`` (its ``unresolved_calls``) and a set of dispatches.
Outputs: a new edge set, and -- the part that matters -- an honest statement of
    whether the promotion *generalises* or merely *memorises* the trace.

THE CIRCULARITY PROBLEM. The promotion rule is learned from dispatches ``D``.
Scoring the promoted graph against the same ``D`` is a tautology: every promoted
    edge is in ``D`` by construction, so precision on that subset is 1.0 no
    matter how bad the rule is. This module therefore ships a two-fold
    HELD-OUT protocol: the oracle attributes dispatches per harness target,
    targets split into two folds, the rule is learned on fold A only and
    scored on fold B. Fold B contains callers that were never invoked in fold
    A, so a rule that merely memorised fold A scores zero there.

Two promotion modes, deliberately separated because they differ in exactly the
way the held-out protocol is designed to expose (proved in equations.md row 9):

* MODE A -- edge promotion. Bind an unresolved call at caller ``c`` to a symbol
  observed leaving ``c``. Sound, and precision-monotone (promoted edges are a
  subset of ``D``), but it CANNOT generalise: no rule is ever instantiated for a
  caller absent from the training fold, so held-out recall for unseen callers is
  identically 0.
* MODE B -- name promotion. Learn ``bare callee name -> symbol`` and apply it to
  EVERY unresolved site with that name, including callers never executed. This
  is what can reach unseen callers. Its failure mode is name collision, removed
  by dropping any name that was ever observed binding to two symbols.
"""
from __future__ import annotations

import importlib
import os
import sys
from typing import Dict, Set, Tuple

# The NN_ filename convention makes these unimportable by name, and running this
# file directly puts src/ -- not the repo root -- on sys.path. Same bootstrap the
# research runner uses.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

Symbol = str
Dispatch = Tuple[Symbol, Symbol]


def bare(sym: Symbol) -> str:
    """Last dotted component of a symbol -- the only part a trace attribute shares."""
    return sym.rsplit(".", 1)[-1]


def learn_name_rules(train: Set[Dispatch]) -> Dict[str, Symbol]:
    """MODE B rule set: bare callee name -> the single symbol it resolved to.

    A name seen binding to two distinct symbols is DROPPED, not guessed. That
    is the guard from equations.md row 9: it trades coverage for a hard
    guarantee that a promoted edge names a symbol that really was dispatched
    under that name somewhere.
    """
    seen: Dict[str, Set[Symbol]] = {}
    for _, dst in train:
        seen.setdefault(bare(dst), set()).add(dst)
    return {n: next(iter(s)) for n, s in seen.items() if len(s) == 1}


def promote_mode_a(cpg, train: Set[Dispatch]) -> Set[Dispatch]:
    """MODE A: per-caller exact binding from observed dispatches.

    Fires only for callers present in ``train``, which is precisely why its
    held-out recall against an unseen caller is 0 by construction.
    """
    by_caller: Dict[Symbol, Dict[str, Symbol]] = {}
    for caller, dst in train:
        by_caller.setdefault(caller, {})[bare(dst)] = dst
    out: Set[Dispatch] = set()
    for caller, raw in cpg.unresolved_calls:
        target = by_caller.get(caller, {}).get(raw)
        if target is not None:
            out.add((caller, target))
    return out


def promote_mode_b(cpg, rules: Dict[str, Symbol]) -> Set[Dispatch]:
    """MODE B: apply the learned name rule to every unresolved call site."""
    out: Set[Dispatch] = set()
    for caller, raw in cpg.unresolved_calls:
        target = rules.get(raw)
        if target is not None:
            out.add((caller, target))
    return out


def coverage_ceiling(cpg, rules: Dict[str, Symbol]) -> float:
    """Share of unresolved call SITES whose name the training fold ever saw.

    This is the measured ceiling of held-out promotion: a site whose callee name
    never appeared in the training fold can never be promoted, no matter how
    good the rule is. Reported so the residual misses are attributed to a
    quantified limit rather than to a vague "needs more work".
    """
    sites = {raw for _, raw in cpg.unresolved_calls if raw != "<complex>"}
    if not sites:
        return 1.0
    return len(sites & set(rules)) / len(sites)


def apply_promotion(cpg, promoted: Set[Dispatch]):
    """Return ``cpg`` with ``promoted`` edges merged in and the index rebuilt.

    Mutates in place on purpose: the caller owns the instance and re-running the
    static build is the only way to get a pristine one, which is what the paired
    static-vs-promoted control does.
    """
    cpg.call_edges |= promoted
    cpg.nodes |= {d for _, d in promoted}
    return cpg.finalise()


def heldout(
    predicted: Set[Dispatch],
    eval_dispatches: Set[Dispatch],
    eval_covered: Set[Symbol],
) -> Dict[str, float]:
    """Score a prediction set against a fold it was never trained on.

    ``heldout_recall`` = share of the evaluation fold's dispatches predicted.
    ``heldout_precision`` restricts the denominator to predicted edges whose
    CALLER was covered in the evaluation fold -- an edge from an unexercised
    caller is absent from the fold by construction, so leaving it in the
    denominator would count a guaranteed miss as a false edge and bias the
    number low (equations.md row 9).
    """
    evaluable = {e for e in predicted if e[0] in eval_covered}
    return {
        "heldout_recall": round(
            len(predicted & eval_dispatches) / len(eval_dispatches), 4
        )
        if eval_dispatches
        else 0.0,
        "heldout_precision": round(
            len(evaluable & eval_dispatches) / len(evaluable), 4
        )
        if evaluable
        else 0.0,
        "heldout_evaluable_edges": len(evaluable),
    }


def precision_of(predicted: Set[Dispatch], truth: Set[Dispatch]) -> float:
    """Plain precision of ``predicted`` against ``truth`` (truth may be a fold)."""
    return 1.0 if not predicted else len(predicted & truth) / len(predicted)


def recall_of(predicted: Set[Dispatch], truth: Set[Dispatch]) -> float:
    """Plain recall of ``predicted`` against ``truth`` (truth may be a fold)."""
    return 0.0 if not truth else len(predicted & truth) / len(truth)


def split_caller_recall(
    promoted: Set[Dispatch],
    train: Set[Dispatch],
    eval_dispatches: Set[Dispatch],
) -> Dict[str, float]:
    """Split held-out recall into SEEN vs UNSEEN callers.

    This is the measurement that separates "learned a rule" from "memorised the
    trace". MODE A can only ever populate the seen half; a technique that moves
    the unseen half has generalised.
    """
    seen_callers = {c for c, _ in train}
    out: Dict[str, float] = {}
    for label, callers in (
        ("seen", seen_callers),
        ("unseen", {c for c, _ in eval_dispatches} - seen_callers),
    ):
        truth = {d for d in eval_dispatches if d[0] in callers}
        out[f"n_dispatch_{label}_callers"] = float(len(truth))
        # A fold with no unseen-caller dispatches reports 0.0, never 1.0: an
        # untested fold must not be able to masquerade as a success.
        out[f"recall_{label}_callers"] = (
            round(len(promoted & truth) / len(truth), 4) if truth else 0.0
        )
    return out


def _self_check() -> None:
    """Assert the two modes differ exactly where the theory says they do.

    The theorem being checked (equations.md row 9): MODE A cannot reach a caller
    absent from its training fold; MODE B can. If this ever inverts, the held-out
    protocol has stopped being the thing it claims to be.
    """
    global _MISSING
    cpg_mod = importlib.import_module("src.00_cpg_static")
    files = {
        "store.py": (
            "class Store:\n"
            "    def query(self, uid):\n        return {'uid': uid}\n"
            "store = Store()\n"
        ),
        "users.py": (
            "from store import store\n"
            "class UserRepo:\n"
            "    def __init__(self, s):\n        self.s = s\n"
            "    def fetch(self, uid):\n        return self.s.query(uid)\n"
        ),
        "audit.py": (
            "from store import store\n"
            "class AuditRepo:\n"
            "    def __init__(self, s):\n        self.s = s\n"
            "    def scan(self, uid):\n        return self.s.query(uid)\n"
        ),
    }
    cpg = cpg_mod.build_cpg(files)
    # both attribute-on-instance sites are recorded with their caller scope
    assert ("users.UserRepo.fetch", "query") in cpg.unresolved_calls
    assert ("audit.AuditRepo.scan", "query") in cpg.unresolved_calls

    train = {("users.UserRepo.fetch", "store.Store.query")}  # audit never ran
    eval_d = {("audit.AuditRepo.scan", "store.Store.query")}
    eval_cov = {"audit.AuditRepo.scan", "store.Store.query"}

    rules = learn_name_rules(train)
    assert rules == {"query": "store.Store.query"}, rules
    assert coverage_ceiling(cpg, rules) == 1.0

    a_edges = promote_mode_a(cpg, train)
    b_edges = promote_mode_b(cpg, rules)
    # MODE A reaches only the trained caller
    assert a_edges == {("users.UserRepo.fetch", "store.Store.query")}, a_edges
    # MODE B transfers the name rule to the untrained caller
    assert ("audit.AuditRepo.scan", "store.Store.query") in b_edges, b_edges

    # ...and that is the whole difference, as measured on the held-out fold
    ho_a = heldout(a_edges, eval_d, eval_cov)
    ho_b = heldout(b_edges, eval_d, eval_cov)
    assert ho_a["heldout_recall"] == 0.0, ho_a
    assert ho_b["heldout_recall"] == 1.0, ho_b

    # name collision is refused, not guessed
    collide = learn_name_rules(
        {("a.f", "m1.query"), ("b.g", "m2.query")}
    )
    assert "query" not in collide, collide
    split = split_caller_recall(b_edges, train, eval_d)
    assert split["recall_unseen_callers"] == 1.0, split
    print("02_trace_promote self-check OK", {"a": ho_a, "b": ho_b, "split": split})


if __name__ == "__main__":
    _self_check()
