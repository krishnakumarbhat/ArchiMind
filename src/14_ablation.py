"""Run 14 (N16): give eq. row 40 a non-empty denominator or retract it.

Run 13 published L1 -- an omission-only oracle charges the static predictor an
UPPER BOUND on its false positives, and a truncated gold standard MANUFACTURES
false positives in the instrument meant to audit it -- and measured it on three
fixtures, obtaining ``n_manufactured_false_positives = 0`` and ``deflation =
0.0`` on all three. That is a vacuous truth: the theorem's own predicted effect
never occurred, so nothing was tested. The cause is mechanical and is in run
13's driver: the "truncated" side was ``DYN.run_oracle(py)`` under the WALL-CLOCK
bound, which never expires on fixtures this small, so ``truth_sets_equal`` was
``True`` everywhere and the contrast the law needs did not exist.

An adversarial referee also found L1 is overstated as written. The bound is
NON-NEGATIVE, not strict, and it is tight exactly when

    ``predicted & (truth_complete - truth_observed) == {}``

because an omitted dispatch only inflates the count if the predictor had
predicted it. So there is a case where the oracle is incomplete, the omission is
real, and the measured false-positive count is unchanged -- which is a
counterexample to the word "strictly" as it appears in the run-13 record.

This module adds the two laws that make the claim testable and falsifiable:

  * ``tightness``      -- the iff above, written independently of
                          ``13_oracle_channel.manufactured_false_positives`` so
                          the two can be cross-checked against each other;
  * ``direction_needs_the_precondition`` -- L1's direction holds ONLY for an
                          omission-only oracle, and an oracle that invents a
                          dispatch reverses it. This is the falsifier run 13
                          asserted but never ran.

Nothing here executes third-party code; the caller supplies fixture sources.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Set, Tuple

Dispatch = Tuple[str, str]


def tightness(
    predicted: Set[Dispatch],
    truth_observed: Set[Dispatch],
    truth_complete: Set[Dispatch],
) -> Dict[str, Any]:
    """Is the measured false-positive count inflated, and by exactly what?

    ``fe_obs - fe_true == predicted & (truth_complete - truth_observed)`` as set
    identities, so the bound is TIGHT iff that intersection is empty. The
    condition is stated on the *omission* set rather than on the two false-edge
    sets because the omission set is the one an ablation controls: an ablation
    that omits only symbols the predictor did not predict cannot move the
    number, however complete or incomplete the oracle is.
    """
    omitted = set(truth_complete) - set(truth_observed)
    omitted_and_predicted = set(predicted) & omitted
    fe_true = set(predicted) - set(truth_complete)
    fe_obs = set(predicted) - set(truth_observed)
    return {
        "omission_only_precondition_holds": set(truth_observed) <= set(truth_complete),
        "n_omitted": len(omitted),
        "n_omitted_and_predicted": len(omitted_and_predicted),
        "bound_is_tight": not omitted_and_predicted,
        "bound_is_loose": bool(omitted_and_predicted),
        "identity_holds": (fe_obs - fe_true) == omitted_and_predicted,
        "inflation": len(fe_obs) - len(fe_true),
        "verdict": (
            "TIGHT: the oracle is incomplete but the measured count is exact, so "
            "'incompleteness MANUFACTURES false positives' is FALSE as stated -- "
            "incompleteness manufactures them only for symbols the predictor "
            "predicted."
            if not omitted_and_predicted
            else "LOOSE: the measured count is inflated by exactly the omitted "
            "dispatches the predictor had predicted."
        ),
    }


def direction_needs_the_precondition(
    predicted: Set[Dispatch],
    truth_observed: Set[Dispatch],
    truth_complete: Set[Dispatch],
) -> Dict[str, Any]:
    """Does the upper-bound direction survive an oracle that INVENTS dispatches?

    ``T_obs subset T`` is what licenses ``prec_obs <= prec_true``. Drop the
    subset and the direction can reverse -- but only for an invention that lands
    ON a predicted edge. An invented edge the predictor did not predict lies
    outside both the numerator and the denominator and moves no number at all,
    so "the oracle invented something" is not by itself a violation; the
    violation is the instrument agreeing with the predictor about an edge that
    never happened. That is the direction worth guarding, because it means the
    instrument flatters the very predictor it exists to audit.

    This is the falsifier for the precondition, and the reason L1 is a
    conditional law.
    """
    invented = set(truth_observed) - set(truth_complete)
    fe_true = set(predicted) - set(truth_complete)
    fe_obs = set(predicted) - set(truth_observed)
    n_true_pos = len(set(predicted) & set(truth_complete))
    n_obs_pos = len(set(predicted) & set(truth_observed))
    prec_true = n_true_pos / len(predicted) if predicted else 1.0
    prec_obs = n_obs_pos / len(predicted) if predicted else 1.0
    # The exact condition. An invention only reverses L1 if it pushes the
    # observed true-positive count ABOVE the true one. Two independent reasons
    # it can fail to, both measured on this run's fixtures:
    #   (a) the invented edge is not one the predictor claimed, so it lies
    #       outside the numerator and the denominator and moves nothing;
    #   (b) the oracle is so truncated that the observed count has HEADROOM --
    #       n_true_pos - n_obs_pos slots an invention can fill without reaching
    #       the truth. At event budget 50 the oracle observed 0 of 10 dispatches,
    #       so precision sat at its floor and a single invention could not
    #       exceed the true 0.4.
    # So the precondition is NECESSARY and NOT SUFFICIENT, and the sufficient
    # condition is the iff below rather than the subset relation.
    headroom = n_true_pos - n_obs_pos
    if not invented:
        verdict = "precondition held; nothing to falsify"
    elif prec_obs > prec_true:
        verdict = (
            "L1's direction REVERSES: the invented dispatch was one the predictor "
            "claimed and it never happened, so the measured false-edge count fell "
            "and the measured precision rose above the true one. The instrument "
            "flattered the predictor it exists to audit, so L1 is a law about "
            "OMISSION-ONLY oracles, not about dynamic oracles in general."
        )
    elif headroom > 0:
        verdict = (
            "precondition VIOLATED, direction SURVIVES, and the reason is "
            "HEADROOM: the truncated oracle had %d unclaimed true-positive slots, "
            "so the invention filled one without reaching the true count. "
            "Truncation PROTECTS the direction against invention; only a near-"
            "complete oracle can be flattered this way." % headroom
        )
    else:
        verdict = (
            "precondition VIOLATED, direction SURVIVES: the invented dispatch was "
            "not one the predictor claimed, so it lies outside both the numerator "
            "and the denominator and moves no number."
        )
    return {
        "n_invented": len(invented),
        "precondition_violated": bool(invented),
        "false_edge_count_deflated": len(fe_obs) < len(fe_true),
        "precision_inflated": prec_obs > prec_true,
        "precision_true": prec_true,
        "precision_observed": prec_obs,
        "direction_survives": prec_obs <= prec_true,
        "n_true_positives": n_true_pos,
        "n_observed_positives": n_obs_pos,
        "headroom": headroom,
        "reversal_condition": "n_observed_positives > n_true_positives",
        "violating_the_precondition_is_sufficient": (
            None if not invented else bool(prec_obs > prec_true)
        ),
        "verdict": verdict,
    }


def sweep_is_the_experiment(predicted: Set[Dispatch], rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Did the ablation actually move the number, or is this another vacuous truth?

    Run 13's failure was a law reported on fixtures where its effect could not
    occur. The check that would have caught it is cheap: an incomplete oracle
    exists somewhere in the sweep, and at least one row where an omission landed
    on a predicted symbol, so ``n_manufactured_false_positives > 0`` is
    witnessed rather than assumed.
    """
    rows = list(rows)
    incomplete = [r for r in rows if r.get("n_truth_observed", 0) < r.get("n_truth_complete", 0)]
    loose = [r for r in rows if r.get("bound_is_loose")]
    tight = [r for r in rows if r.get("bound_is_tight") and r.get("n_omitted", 0) > 0]
    return {
        "n_rows": len(rows),
        "n_rows_with_real_omission": len(incomplete),
        "n_loose_rows": len(loose),
        "n_tight_despite_omission_rows": len(tight),
        "max_manufactured": max((r.get("n_manufactured_false_positives", 0) for r in rows), default=0),
        "max_deflation": max((r.get("deflation", 0.0) for r in rows), default=0.0),
        "both_branches_witnessed": bool(loose) and bool(tight),
        "non_vacuous": bool(incomplete) and bool(loose),
        "verdict": (
            "NON-VACUOUS: an omission landed on a predicted symbol, so the "
            "inflation L1 predicts was observed rather than assumed."
            if incomplete and loose
            else "STILL VACUOUS: no omission in this sweep touched a predicted "
            "symbol, so L1's predicted effect remains unwitnessed."
        ),
    }


def self_check() -> Dict[str, bool]:
    """Break every claim above. A law that cannot fail is not a law."""
    d1, d2, d3 = ("a", "T.a"), ("b", "T.b"), ("c", "T.c")
    # Complete oracle: nothing omitted, bound tight, direction holds.
    t0 = tightness({d1, d2}, {d1, d2, d3}, {d1, d2, d3})
    # Incomplete oracle omitting a PREDICTED dispatch: loose, inflated by 1.
    t1 = tightness({d1, d2}, {d2, d3}, {d1, d2, d3})
    # Incomplete oracle omitting only an UNPREDICTED dispatch: tight, no
    # inflation. This is the counterexample to the word "strictly".
    t2 = tightness({d1, d2}, {d1, d2}, {d1, d2, d3})
    # Omission-only oracle: direction holds.
    p0 = direction_needs_the_precondition({d1, d2}, {d1, d2, d3}, {d1, d2, d3})
    # Inventing oracle. The invention must land ON a PREDICTED edge to matter:
    # an invented edge the predictor did not predict is outside both the
    # numerator and the denominator and moves nothing. Here d1 is predicted and
    # truly never dispatched, and the oracle reports it anyway, so the measured
    # false-edge count falls to 0 and the measured precision rises to 1.0.
    p1 = direction_needs_the_precondition({d1, d2}, {d1, d2}, {d2, d3})
    rows = [
        {"n_truth_observed": 3, "n_truth_complete": 3, "n_manufactured_false_positives": 0, "deflation": 0.0, "bound_is_tight": True, "n_omitted": 0},
        {"n_truth_observed": 2, "n_truth_complete": 3, "n_manufactured_false_positives": 1, "deflation": 0.5, "bound_is_loose": True, "n_omitted": 1},
        {"n_truth_observed": 2, "n_truth_complete": 3, "n_manufactured_false_positives": 0, "deflation": 0.0, "bound_is_tight": True, "n_omitted": 1},
    ]
    s0 = sweep_is_the_experiment(set(), rows)
    return {
        "tight_when_complete": t0["bound_is_tight"] and t0["inflation"] == 0,
        "loose_when_omission_hits_prediction": t1["bound_is_loose"] and t1["inflation"] == 1,
        "TIGHT_despite_a_real_omission": t2["bound_is_tight"] and t2["n_omitted"] == 1 and t2["inflation"] == 0,
        "strictly_is_FALSE_as_stated": t2["n_omitted"] > 0 and t2["inflation"] == 0,
        "set_identity_holds": t1["identity_holds"] and t2["identity_holds"] and t0["identity_holds"],
        "precondition_precondition_holds_when_complete": not p0["precondition_violated"],
        "direction_REVERSES_when_oracle_invents": p1["precondition_violated"] and p1["precision_inflated"] and not p1["direction_survives"],
        "invention_off_the_prediction_moves_nothing": (
            # d1 really was dispatched; the oracle invents z, which the
            # predictor never claimed. The subset relation is broken, so the
            # precondition IS violated, yet every number is unchanged. Violating
            # the precondition is necessary for the reversal and not sufficient:
            # what reverses the direction is an invention ON a predicted edge.
            direction_needs_the_precondition({d1}, {d1, ("z", "T.z")}, {d1, d2})[
                "precondition_violated"
            ]
            and not direction_needs_the_precondition(
                {d1}, {d1, ("z", "T.z")}, {d1, d2}
            )["precision_inflated"]
        ),
        # Guards the defect this module was written with: a verdict string
        # keyed on the precondition instead of on the measured reversal, which
        # printed "REVERSES" beside direction_survives = True. The string and the
        # numbers are now asserted to agree, on both branches.
        "verdict_agrees_with_the_numbers_when_reversed": (
            "REVERSES" in p1["verdict"]
        ) == p1["precision_inflated"],
        "verdict_agrees_with_the_numbers_when_it_survives": (
            "SURVIVES" in direction_needs_the_precondition(
                {d1}, {d1, ("z", "T.z")}, {d1, d2}
            )["verdict"]
        ) == (not direction_needs_the_precondition(
            {d1}, {d1, ("z", "T.z")}, {d1, d2}
        )["precision_inflated"]),
        # Reason (b), measured on this run's escape fixture at event budget 50:
        # a truncated oracle has headroom, so an invention that lands OFF the
        # prediction cannot reverse the direction. Headroom is the shield, and
        # it is exactly what truncation creates.
        "headroom_shields_a_truncated_oracle": (
            lambda r: r["precondition_violated"]
            and r["direction_survives"]
            and r["headroom"] > 0
            and "HEADROOM" in r["verdict"]
        )(direction_needs_the_precondition({d1, d2}, {d1, ("z", "T.z")}, {d1, d2, d3})),
        "reversal_needs_headroom_to_go_negative": p1["headroom"] < 0,
        "sweep_sees_both_branches": s0["both_branches_witnessed"],
        "sweep_is_non_vacuous": s0["non_vacuous"],
        "sweep_detects_the_vacuous_case": not sweep_is_the_experiment(set(), rows[:1])["non_vacuous"],
    }
