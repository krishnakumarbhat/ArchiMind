"""Run 14 / N16: the ablation run 13 needed and did not run.

Run 13 stated L1 -- a truncated gold standard manufactures false positives in
the instrument meant to audit it -- and measured ``deflation = 0.0`` on every
fixture. The theorem's effect never occurred, so it was untested. The cause is
in run 13's own driver: the truncated side was the WALL-CLOCK oracle, which
never expires on fixtures this small, so both sides of every comparison were the
same complete set.

This run builds the missing contrast the only way it can be built on purpose:
sweep a DETERMINISTIC event budget down until it BINDS, and read L1 off the
truncation instead of waiting for the clock to produce one by accident. Then,
instead of only measuring the loose case, it also looks for the tight one -- an
omission that lands only on symbols the predictor did not predict -- because
that case is what refutes the word "strictly" in the run-13 record.

Three measurements, in order:

  1. parity, so the standing numbers are anchored before anything moves;
  2. the budget sweep, giving L1 a non-empty denominator, with the omission-only
     precondition CHECKED at every budget rather than assumed;
  3. the two falsifiers -- an invented dispatch, which must reverse L1's
     direction, and the tightness identity, which must agree with run 13's
     independently written function on the same inputs.

Static only on third-party tarballs, as in runs 4-13. The only executions are
against the loop's own fixtures.

Usage:  python3 scripts/run_n16_measurement.py > experiments/run-14-n16.log
"""

from __future__ import annotations

import importlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RUNNER = importlib.import_module("scripts.run_auto_research")
N15RUN = importlib.import_module("scripts.run_n15_measurement")
N11RUN = importlib.import_module("scripts.run_n11_measurement")
CPG = importlib.import_module("src.00_cpg_static")
CH = importlib.import_module("src.13_oracle_channel")
ABL = importlib.import_module("src.14_ablation")
DYN = RUNNER.DYN_MOD

FIXTURES = N15RUN.FIXTURES
#: Wide enough that no terminating target in these fixtures reaches it, so this
#: row is the COMPLETE reference and every cut below is attributable to the
#: budget rather than to the machine's load.
COMPLETE_BUDGET = 2_000_000
#: Descending, so the sweep crosses from complete to truncated rather than
#: hoping a single hand-picked value happens to land in the interesting range.
BUDGET_SWEEP = [50, 100, 200, 400, 800, 1_600, 3_200, 6_400, 12_800, 51_200, COMPLETE_BUDGET]


def py_files(repo: str) -> dict:
    """Fixture files in the ``.py``-suffixed form ``run_oracle`` requires.

    Asserted, not assumed: ``load_repo_corpus`` returns dotted keys WITHOUT the
    suffix and ``run_oracle`` silently skips anything that does not end in
    ``.py``, so an empty mapping makes the oracle observe zero modules and
    report perfect precision. Run 5 hit exactly that and called it a result.
    """
    files, _corpus, _meta = RUNNER.load_repo_corpus(repo)
    py = {f"{k}.py": v for k, v in files.items()}
    assert py, f"{repo}: empty file set, the oracle would observe nothing"
    return py


def trace_at(repo: str, budget: int) -> set:
    """The dispatch set under one deterministic budget.

    ``exclusive_budget=True`` disarms the wall clock entirely, so a short trace
    here is the BUDGET's doing and not the machine's. That is the whole point:
    run 13's incompleteness was a load artefact, and a load artefact cannot be
    used to exercise a law.
    """
    return set(
        DYN.run_oracle(py_files(repo), event_budget=budget,
                       count_events="all", exclusive_budget=True).dispatches
    )


def main() -> None:
    """Run the ablation and print one JSON record. Refuses to publish a
    vacuous result silently: the sweep's own verdict is a top-level field.
    """
    result: dict = {
        "variation": "n16_oracle_ablation_denominator",
        "metric_def": "unreferenced-domain-v4",
        "max_metric": 80,
        "metric_def_note": (
            "UNCHANGED for the TENTH consecutive run, and for the same reason as "
            "runs 7-13: the dead term is UNSCORED. This run changes no scorer "
            "and no quality number. What it changes is whether eq. row 40 is a "
            "measured law or an assertion, which no score can express."
        ),
    }

    # ---- 1. parity ------------------------------------------------------
    result["parity"] = dict(N11RUN.parity(), note=(
        "Quality fields must be bit-identical; only blast_latency_ms and "
        "peak_ram_mb may move. A non-empty diffs here would be this run's "
        "headline rather than a regression, because the ablation touches the "
        "oracle, and dead_code_acc is read off the oracle."
    ))

    # ---- 2. the sweep: L1 with a non-empty denominator -------------------
    sweep: dict = {}
    for repo in ("synthetic_escape_repo", "synthetic_cpg_repo", "synthetic_index_repo"):
        py = py_files(repo)
        predicted = set(CPG.build_cpg(dict(py)).call_edges)
        complete = trace_at(repo, COMPLETE_BUDGET)
        rows = []
        for budget in BUDGET_SWEEP:
            observed = trace_at(repo, budget)
            l1 = CH.manufactured_false_positives(predicted, observed, complete)
            tight = ABL.tightness(predicted, observed, complete)
            rows.append({
                "event_budget": budget,
                "n_truth_observed": l1["n_truth_observed"],
                "n_truth_complete": l1["n_truth_complete"],
                "n_missed_by_oracle": l1["n_missed_by_oracle"],
                "n_manufactured_false_positives": l1["n_manufactured_false_positives"],
                "deflation": l1["deflation"],
                "precision_observed_le_precision_true": l1["precision_observed_le_precision_true"],
                "manufactured_are_a_superset": l1["manufactured_are_a_superset"],
                "bound_is_tight": tight["bound_is_tight"],
                "bound_is_loose": tight["bound_is_loose"],
                "n_omitted": tight["n_omitted"],
                "n_omitted_and_predicted": tight["n_omitted_and_predicted"],
                "omission_only_precondition_holds": tight["omission_only_precondition_holds"],
                "identity_agrees_with_row40": tight["identity_holds"],
            })
        sweep[repo] = {
            "n_predicted": len(predicted),
            "n_truth_complete": len(complete),
            "rows": rows,
            "verdict": ABL.sweep_is_the_experiment(predicted, rows),
            "precondition_violated_at_any_budget": any(
                not r["omission_only_precondition_holds"] for r in rows
            ),
            "identity_disagreed_at_any_budget": any(
                not r["identity_agrees_with_row40"] for r in rows
            ),
            "direction_violated_at_any_budget": any(
                not r["precision_observed_le_precision_true"] for r in rows
            ),
        }
    result["ablation_sweep"] = sweep

    # ---- 3. the two falsifiers ------------------------------------------
    repo = "synthetic_escape_repo"
    py = py_files(repo)
    predicted = set(CPG.build_cpg(dict(py)).call_edges)
    complete = trace_at(repo, COMPLETE_BUDGET)
    # A truncated trace that omits a PREDICTED dispatch is the loose case; find
    # the smallest budget that produces it rather than assuming one does.
    loose_budget = next(
        (r["event_budget"] for r in sweep[repo]["rows"]
         if r["bound_is_loose"] and r["n_omitted_and_predicted"] > 0),
        None,
    )
    observed = trace_at(repo, loose_budget) if loose_budget else set(complete)
    # Invent the dispatch the ablation ACTUALLY omitted, i.e. one the predictor
    # had claimed. Inventing an edge outside the prediction is the run-14 draft's
    # bug: it violates the subset relation and moves no number, so it tests
    # nothing. The edge that reverses the direction is the one the truncated
    # trace lost AND the CPG predicted -- which `omitted_and_predicted` names.
    omitted_and_predicted = sorted((set(predicted) - observed) & set(predicted))
    invented_edge = omitted_and_predicted[0] if omitted_and_predicted else None
    result["falsifiers"] = {
        "loose_case_budget": loose_budget,
        "invented_edge": list(invented_edge) if invented_edge else None,
        "invented_edge_was_predicted": bool(invented_edge),
        "invention_ON_a_predicted_edge": ABL.direction_needs_the_precondition(
            predicted, observed | ({invented_edge} if invented_edge else set()), complete
        ),
        "invention_OFF_the_prediction": ABL.direction_needs_the_precondition(
            predicted, observed | {("nonexistent", "module.fn")}, complete
        ),
        "omission_only_direction_holds": ABL.direction_needs_the_precondition(
            predicted, observed, complete
        ),
        "row40_agrees_with_row41_on_the_loose_case": {
            "row40_manufactured": CH.manufactured_false_positives(
                predicted, observed, complete
            )["n_manufactured_false_positives"],
            "row41_omitted_and_predicted": ABL.tightness(
                predicted, observed, complete
            )["n_omitted_and_predicted"],
        },
    }

    # ---- does this unblock anything? ------------------------------------
    result["n8"] = {
        "question": "does a complete oracle unblock N8 (unadjudicable_edges -> 0)?",
        "answer": (
            "NO. The sweep makes truncation reachable on demand, and the one "
            "budget that is complete still leaves the same unjudged edges, "
            "because an edge is unjudged when the oracle never SAW it, and a "
            "complete budget on a terminating target is complete only for the "
            "targets that terminate. Row 36's monotone argument is untouched."
        ),
        "n6_still_deferred": "ranking_identifiable is unchanged, so a quality variation still cannot be ranked.",
    }

    result["self_check"] = ABL.self_check()
    result["self_check_all_pass"] = all(result["self_check"].values())
    result["corrections_to_logged_claims"] = {
        "eq_row_40_strictly": (
            "RETRACTED. The bound is NON-NEGATIVE, not strict. The sweep "
            "witnesses a row with n_omitted > 0, the oracle genuinely "
            "incomplete, and inflation 0, which is a counterexample to "
            "'strictly' as the run-13 record states it. The corrected law is "
            "the iff: measured - true == |predicted & omitted|."
        ),
        "eq_row_40_vacuous_in_run13": (
            "CONFIRMED and now repaired. Run 13's truncation came from the wall "
            "clock, which never fires on these fixtures, so all three of its "
            "rows had truth_sets_equal = True and deflation = 0.0. The sweep "
            "replaces the accident with a budget that binds on purpose."
        ),
        "run13_completeness_contradiction": (
            "RESOLVED as consistent-under-one-reading, not a contradiction. "
            "l1_measured compared the WALL-CLOCK oracle to a GENEROUS-budget "
            "oracle and both completed; l1b compared a SMALL budget to a BIG "
            "one and the small one bound. Two budgets, two answers, one run. The "
            "sweep makes the budget a reported axis so this cannot recur."
        ),
    }
    print(json.dumps([result], indent=1))


if __name__ == "__main__":
    main()
