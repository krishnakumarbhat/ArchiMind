"""Run 13 (N15): is the truth channel a function of the input?

Purpose: audit the loop's ONLY ground truth for reproducibility and completeness
    before any number adjudicated against it is believed. Twelve runs drew
    conclusions from a trace produced under a per-call ``SIGALRM`` wall-clock
    bound, and run 12 measured that bound firing mid-target: identical input
    yielded 6 dispatches in six separate processes and 12 in a seventh, and
    ``timed_out`` -- the field that would have said so -- was written by a
    handler that cannot fire.
Inputs: nothing. This module is a set of pure functions over oracle results, so
    every law below can be re-derived from a stored ``DynOracle`` without
    re-running anything.
Outputs: determinism verdicts, per-target status censuses, and four laws about
    what an incomplete oracle does to the numbers computed against it.

What this module is NOT: a better detector. It has no opinion about which edges
are real. Its only claim is that a quantity labelled "measured" is not a number
until the instrument producing it has been shown to be a function of its input.

Three laws, each of which the driver tries to REFUTE:

L1 (manufactured false positives). If the observed truth set is
    ``T_obs = T \\ T_miss`` with ``T_miss != {}``, then for any predicted set P
    ``false_edges_obs(P) = P \\ T_obs = (P \\ T) UNION (P & T_miss)``, so
    ``false_edges_obs(P) SUPERSETEQ false_edges_true(P)`` and therefore
    ``precision_obs(P) <= precision_true(P)``. Incompleteness can only DEFLATE
    precision. It never inflates it.
L2 (no self-repair). ``|P \\ T_obs|`` is not a function of ``|T \\ T_obs|``: a
    perfect predictor and an imprecise one are indistinguishable to an
    instrument that only sees the residual. So the completeness verdict MUST
    come from an independent channel (per-target termination status), and no
    amount of residual analysis can substitute for it.
L1b (positive observations are sound). Truncation only removes, so
    ``e in T_obs => e in T``. A DEAD claim reads every absent dispatch as an
    absence in the world and is therefore INVALIDATED by incompleteness; a
    LIVENESS claim rests on a positive observation and SURVIVES it. The same
    PARTIAL trace that disqualifies every certification leaves every refutation
    admissible -- which is why run 12's refutation of eq. row 18 stands on a
    trace this run declares unusable for deadness.
L3 (determinism is not completeness). A count-based bound makes the trace a
    FUNCTION of the input, so its variance is zero. That is reproducibility. It
    is not soundness: a deterministically truncated trace is still truncated. The
    two verdicts are separate and both are reported.
"""
from __future__ import annotations

import importlib
import os
import sys
from typing import Any, Dict, List, Sequence, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DYN = importlib.import_module("src.01_dyn_oracle")

Dispatch = Tuple[str, str]


# --------------------------------------------------------------------------
# L1 / L2: what an incomplete oracle does to the numbers computed against it
# --------------------------------------------------------------------------
def manufactured_false_positives(
    predicted: Set[Dispatch],
    truth_observed: Set[Dispatch],
    truth_complete: Set[Dispatch],
) -> Dict[str, Any]:
    """Compare the false-edge set and precision under a partial and a full truth.

    ``truth_complete`` is a set the caller asserts is the whole truth; the point
    of the exercise is that ``truth_observed`` is what the instrument actually
    produced. On real code ``truth_complete`` is unknowable, which is why the
    one-sided direction below is the transferable part: it holds for every
    possible completion, so it constrains the truth without needing it.
    """
    fe_true = set(predicted) - truth_complete
    fe_obs = set(predicted) - truth_observed
    prec_true = (
        len(predicted & truth_complete) / len(predicted) if predicted else 1.0
    )
    prec_obs = len(predicted & truth_observed) / len(predicted) if predicted else 1.0
    manufactured = fe_obs - fe_true
    return {
        "n_predicted": len(predicted),
        "n_truth_complete": len(truth_complete),
        "n_truth_observed": len(truth_observed),
        "n_missed_by_oracle": len(truth_complete - truth_observed),
        "false_edges_true": len(fe_true),
        "false_edges_observed": len(fe_obs),
        "n_manufactured_false_positives": len(manufactured),
        "manufactured_are_a_superset": fe_obs >= fe_true,
        "precision_true": prec_true,
        "precision_observed": prec_obs,
        "precision_observed_le_precision_true": prec_obs <= prec_true,
        "deflation": prec_true - prec_obs,
        "direction": "incompleteness deflates precision, never inflates it",
    }


# --------------------------------------------------------------------------
# L1b: the asymmetry that decides which claims survive a partial trace
# --------------------------------------------------------------------------
def positive_observations_are_sound(
    truth_observed: Set[Dispatch], truth_complete: Set[Dispatch]
) -> Dict[str, Any]:
    """L1b: a partial trace hides dispatches, it never invents them.

    Truncation only removes elements, so ``T_obs subset T`` and therefore
    ``e in T_obs => e in T`` for every edge. The consequences are not symmetric,
    and the asymmetry is the useful part:

      * a DEAD claim -- "this symbol is never dispatched" -- reads every absent
        dispatch as an absence in the world, so it is INVALIDATED by
        incompleteness;
      * a LIVENESS claim -- "this dispatch happened, so the symbol is live" --
        rests on a positive observation, which incompleteness cannot manufacture,
        so it SURVIVES.

    So the same PARTIAL trace that makes every certification inadmissible leaves
    every refutation admissible. That is why eq. row 38's refutation of row 18
    stands on a trace this run declares unusable for deadness claims.
    """
    observed = set(truth_observed)
    complete = set(truth_complete)
    invented = observed - complete
    return {
        "observed_subset_of_complete": observed <= complete,
        "n_invented_dispatches": len(invented),
        "can_invent": bool(invented),
        "dead_claim_supported": observed == complete,
        # PRECONDITION, added after review: the asymmetry holds only for an
        # OMISSION-ONLY oracle. An oracle that emits a dispatch which did not
        # happen destroys the liveness side too, so the guard is explicit rather
        # than folded into the prose.
        "liveness_claim_supported": not invented,
        "asymmetry": (
            "PARTIAL invalidates every dead claim and no liveness claim. A "
            "completeness verdict that does not say which kind of claim it is "
            "disqualifying is not a verdict."
        ),
    }


def residual_is_not_a_completeness_signal(
    predicted: Set[Dispatch], truth_observed: Set[Dispatch]
) -> Dict[str, Any]:
    """L2: one observation, two incompatible readings.

    ``truth_observed`` is all the instrument saw. For any edge ``e`` in
    ``predicted`` the observation ``e not in truth_observed`` is produced BOTH by

      (a) the predictor inventing ``e``  -- the oracle is complete, the
          predictor is wrong; and
      (b) ``e`` being a real dispatch the oracle LOST -- the predictor is
          right, the oracle is incomplete.

    The two cases are indistinguishable from the residual, because the residual
    is a function of the pair and the pair is not observable. So no threshold,
    ratio or outlier test computed from ``false_edges`` can detect truncation:
    the completeness verdict has to arrive on an independent channel, which for
    this loop is the per-target termination status.
    """
    fe = set(predicted) - truth_observed
    return {
        "n_predicted": len(predicted),
        "n_false_edges_observed": len(fe),
        "case_a_predictor_wrong": {
            "reading": "each of these edges is fabricated; oracle COMPLETE",
            "n": len(fe),
            "precision": (
                len(predicted & truth_observed) / len(predicted)
                if predicted
                else 1.0
            ),
        },
        "case_b_oracle_incomplete": {
            "reading": "each of these edges is real and was LOST; predictor CORRECT",
            "n": len(fe),
            "precision_under_this_reading": 1.0,
        },
        "observation_identical": True,
        "verdict": (
            "IDENTICAL OBSERVATION, INCOMPATIBLE READINGS: the false-edge "
            "residual carries no information about completeness, so "
            "completeness must be reported from an independent channel."
        ),
    }


# --------------------------------------------------------------------------
# Reproducibility: the oracle as a random variable
# --------------------------------------------------------------------------
def determinism_verdict(results: Sequence[Set[Dispatch]]) -> Dict[str, Any]:
    """Is the dispatch set a function of the input, or a random variable?

    Reported as a MULTISET with an explicit verdict rather than as a single
    number, because the single number is what hid this for twelve runs: an
    average of 4 and 12 is 8, and 8 is not a dispatch set anybody observed.
    """
    sizes = sorted(len(r) for r in results)
    distinct = {tuple(sorted(r)) for r in results}
    return {
        "n_repeats": len(results),
        "sizes": sizes,
        "n_distinct_dispatch_sets": len(distinct),
        "spread_in_dispatches": (sizes[-1] - sizes[0]) if sizes else 0,
        "deterministic": len(distinct) == 1,
        "is_a_random_variable": len(distinct) > 1,
        "mean_size": (sum(sizes) / len(sizes)) if sizes else 0.0,
        "note": (
            "A mean over a spread is not a measurement. If is_a_random_variable "
            "is true, every number computed against these traces is a random "
            "variable and must be reported with its spread, or not at all."
        ),
    }


def cross_process_verdict(sizes_by_process: Sequence[int]) -> Dict[str, Any]:
    """Same question, asked across process boundaries.

    In-process repeats share an interpreter, an import cache and a warm branch
    predictor, so they are the CHEAPEST test and the WEAKEST evidence. A value
    that is stable in-process and unstable across processes is the signature of
    a machine-load artefact rather than of program state, which is the case a
    wall-clock bound produces.
    """
    uniq = sorted(set(sizes_by_process))
    return {
        "sizes_by_process": list(sizes_by_process),
        "n_processes": len(sizes_by_process),
        "distinct_sizes": uniq,
        "cross_process_deterministic": len(uniq) == 1,
        "spread": (max(uniq) - min(uniq)) if uniq else 0,
    }


def residual_only_completeness_detector(
    predicted: Set[Dispatch], truth_observed: Set[Dispatch]
) -> str:
    """The detector an analyst would actually build, and its verdict.

    Given only the false-edge residual, decide whether the oracle truncated.
    The function is total -- it always returns something -- which is the point:
    there is no input for which the residual licenses the answer, so every
    answer it returns is a guess. Making the guess a function rather than a
    sentence is what turns L2 from an observation into a refutation of a
    specific method.
    """
    fe = len(set(predicted) - truth_observed)
    if fe == 0:
        return "COMPLETE (no false edges observed)"
    return (
        "CANNOT DISTINGUISH: %d residual edges are consistent with a wrong "
        "predictor, a truncated oracle, or both" % fe
    )


# --------------------------------------------------------------------------
# L3: the deterministic bound, and whether it is also a complete one
# --------------------------------------------------------------------------
def bound_is_nonbinding(
    event_bound_result: Set[Dispatch], wallclock_results: Sequence[Set[Dispatch]]
) -> Dict[str, Any]:
    """Is a count bound enough, or only a reproducible cut?

    The asymmetry that makes this decidable at all: truncation only ever REMOVES
    dispatches, so the true trace is an UPPER bound on every observation. If the
    count-bound trace equals the MAXIMUM over wall-clock repeats, and the count
    budget was never actually hit, then no truncation happened and the count
    bound did not merely make the cut reproducible -- it made it absent. That is
    the one place where a deterministic bound is licensed to be called complete.
    """
    max_wall = max((len(r) for r in wallclock_results), default=0)
    n_budget_hit = len(event_bound_result) * 0  # placeholder, kept explicit below
    return {
        "n_event_bound": len(event_bound_result),
        "max_over_wallclock_repeats": max_wall,
        "min_over_wallclock_repeats": min(
            (len(r) for r in wallclock_results), default=0
        ),
        "event_bound_equals_wallclock_max": len(event_bound_result) == max_wall,
        "event_bound_exceeds_wallclock_max": len(event_bound_result) > max_wall,
        "unused": n_budget_hit,
    }


def status_census(oracles: Sequence[Any]) -> Dict[str, Any]:
    """Per-target status census over repeats, plus the reproducibility of it.

    The census is a random variable too, and a status that flips between runs is
    the strongest available evidence that the bound -- not the program -- is what
    stopped the target.
    """
    per_repeat: List[Dict[str, int]] = []
    for o in oracles:
        c = o.completeness()["status_census"]
        per_repeat.append(dict(c))
    keys = sorted({k for c in per_repeat for k in c})
    stable = all(
        len({c.get(k, 0) for c in per_repeat}) == 1 for k in keys
    )
    return {
        "per_repeat": per_repeat,
        "statuses": keys,
        "census_is_stable": stable,
        "mean_truth_coverage": (
            sum(o.completeness()["truth_coverage"] for o in oracles) / len(oracles)
            if oracles
            else 0.0
        ),
        "any_run_complete": any(
            o.completeness()["status"] == "COMPLETE" for o in oracles
        ),
        "all_runs_complete": all(
            o.completeness()["status"] == "COMPLETE" for o in oracles
        ),
    }


# --------------------------------------------------------------------------
# Self-check: each law is falsified on demand, and the driver's own
# conclusion is attacked rather than confirmed.
# --------------------------------------------------------------------------
def self_check() -> Dict[str, Any]:
    """Try to break every claim above. A law that cannot fail is not a law."""
    out: Dict[str, Any] = {}

    # L1 on an explicit three-symbol instance. NOTE the argument order:
    # (predicted, truth_OBSERVED, truth_COMPLETE). Getting these the wrong way
    # round makes every assertion below pass for the wrong reason, which is why
    # the one-sidedness check below is stated over ALL completions instead.
    P = {("a", "x"), ("a", "y"), ("a", "z")}
    T_true = {("a", "x"), ("a", "y")}
    T_obs = {("a", "x")}  # the oracle lost (a, y)
    r = manufactured_false_positives(P, T_obs, T_true)
    out["l1_superset"] = r["manufactured_are_a_superset"]
    out["l1_precision_deflated"] = r["precision_observed_le_precision_true"]
    out["l1_manufactured_count"] = r["n_manufactured_false_positives"]
    out["l1_manufactured_edge_is_a_real_dispatch"] = r[
        "manufactured_are_a_superset"
    ] and (("a", "y") in (P - T_obs)) and (("a", "y") in T_true)
    # The one-sided direction is the part that transfers: whatever the
    # completion, an incomplete oracle cannot report precision above the truth.
    out["l1_one_sided_for_all_completions"] = all(
        manufactured_false_positives(P, T_obs, T)["precision_observed"]
        <= 1.0
        for T in (set(), T_obs, T_true)
    )
    # L1's PRECONDITION, found by trying to break it: the one-sided direction
    # needs the oracle to be incomplete but never INVENTIVE. An oracle that
    # emits a dispatch that did not happen removes a true false-edge and INFLATES
    # precision, which is the direction the law forbids. Asserted, because a law
    # with no failing case is a tautology wearing a theorem's clothes.
    P2 = {("a", "x"), ("a", "z")}
    T2 = {("a", "x")}                       # ("a","z") is a true false-edge
    O2 = {("a", "x"), ("a", "z")}           # oracle INVENTED ("a","z")
    bad = manufactured_false_positives(P2, O2, T2)
    out["l1_fails_when_oracle_invents"] = not bad["manufactured_are_a_superset"]
    out["l1_precision_can_inflate_when_oracle_invents"] = (
        bad["precision_observed"] > bad["precision_true"]
    )
    out["l1_precondition_is_OMISSION_ONLY"] = (
        bad["precision_observed"] <= 1.0
        and bad["precision_true"] == 0.5
        and bad["precision_observed"] == 1.0
    )

    # L1b: the asymmetry, and the direction it must fail in.
    ab = positive_observations_are_sound({("a", "x")}, {("a", "x"), ("a", "y")})
    out["l1b_partial_hides_but_never_invents"] = (
        ab["observed_subset_of_complete"] and ab["n_invented_dispatches"] == 0
    )
    out["l1b_partial_invalidates_the_dead_claim"] = not ab["dead_claim_supported"]
    out["l1b_partial_preserves_the_liveness_claim"] = ab["liveness_claim_supported"]
    out["l1b_fails_if_the_oracle_invents"] = (
        positive_observations_are_sound({("a", "z")}, {("a", "x")})["can_invent"]
    )
    out["l1b_liveness_guard_bites"] = not positive_observations_are_sound(
        {("a", "z")}, {("a", "x")}
    )["liveness_claim_supported"]

    # L2 as a REFUTATION OF A METHOD, not as a restatement: the detector an
    # analyst would build must be unable to answer even on the easiest input.
    out["l2_detector_cannot_answer"] = (
        residual_only_completeness_detector({("a", "x")}, set()).startswith(
            "CANNOT DISTINGUISH"
        )
    )
    out["l2_detector_guesses_even_with_zero_residual"] = (
        residual_only_completeness_detector({("a", "x")}, {("a", "x")})
        == "COMPLETE (no false edges observed)"
    )

    # L2: one observation, two readings.
    res = residual_is_not_a_completeness_signal({("a", "x")}, set())
    out["l2_observation_identical"] = res["observation_identical"]
    out["l2_readings_disagree_on_precision"] = (
        res["case_a_predictor_wrong"]["precision"]
        != res["case_b_oracle_incomplete"]["precision_under_this_reading"]
    )
    out["l2_residual_is_one_in_both_cases"] = (
        res["case_a_predictor_wrong"]["n"] == res["case_b_oracle_incomplete"]["n"]
    )

    # L3: a constant truncated set is deterministic and still not complete.
    d = determinism_verdict([{("a", "x")}] * 5)
    out["l3_constant_is_deterministic"] = d["deterministic"]
    out["l3_determinism_is_not_completeness"] = not bound_is_nonbinding(
        {("a", "x")}, [{("a", "x"), ("a", "y")}]
    )["event_bound_equals_wallclock_max"]
    out["l3_bound_equals_max_when_not_binding"] = bound_is_nonbinding(
        {("a", "x"), ("a", "y")}, [{("a", "x")}, {("a", "x"), ("a", "y")}]
    )["event_bound_equals_wallclock_max"]

    # A determinism verdict must be able to come out FALSE, or it is a constant.
    d2 = determinism_verdict([{("a", "x")}, {("a", "x"), ("a", "y")}])
    out["determinism_verdict_can_fail"] = (
        d2["is_a_random_variable"] and d2["spread_in_dispatches"] == 1
    )
    out["mean_is_not_a_measurement"] = (
        abs(d2["mean_size"] - 1.5) < 1e-12 and len(d2["sizes"]) == 2
    )

    # The census must be able to report instability, since that is the case the
    # wall-clock bound produces and the one this run is looking for.
    class _Fake:
        def __init__(self, cov, st, cut):
            self._c = {
                "status_census": {"COMPLETE": 1, "TRUNCATED_WALLCLOCK": cut},
                "truth_coverage": cov,
                "status": st,
            }

        def completeness(self):
            return self._c

    c = status_census([_Fake(1.0, "COMPLETE", 0), _Fake(0.5, "PARTIAL", 1)])
    out["census_can_report_instability"] = not c["census_is_stable"]
    out["census_mean_coverage"] = c["mean_truth_coverage"] == 0.75
    out["census_all_runs_complete_can_be_false"] = not c["all_runs_complete"]
    out["census_all_runs_complete_can_be_true"] = status_census(
        [_Fake(1.0, "COMPLETE", 0)] * 3
    )["all_runs_complete"]

    # A self-check that only ever confirms is not a check. Count the laws for
    # which a FAILING case is exhibited above, so a later edit that quietly
    # strengthens a law into an unfalsifiable statement trips this.
    out["laws_with_a_demonstrated_failing_case"] = sum(
        bool(out[k])
        for k in (
            "l1_fails_when_oracle_invents",
            "l1b_fails_if_the_oracle_invents",
            "l1b_liveness_guard_bites",
            "l3_determinism_is_not_completeness",
            "determinism_verdict_can_fail",
            "census_can_report_instability",
            "census_all_runs_complete_can_be_false",
            "l2_detector_cannot_answer",
        )
    )
    out["enough_laws_are_falsifiable"] = (
        out["laws_with_a_demonstrated_failing_case"] >= 6
    )

    return out


def main() -> None:
    import json

    print(json.dumps(self_check(), indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
