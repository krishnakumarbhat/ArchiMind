"""Run 11 / N13: the non-executing adjudicator, run as written and then audited.

The node's own success criterion, quoted from the strategy graph: an edge
(caller, callee) is DEFINITIVELY FALSE if ``leaf(callee)`` occurs nowhere in
the caller's body, so ``unadjudicable_edges`` can be shrunk on an untrusted
tarball WITHOUT running the oracle, and soundness is falsifiable on the loop's
own executed fixtures -- "if the filter ever removes a TRUE edge, the node dies
on its own measurement".

So this script does exactly that and nothing kinder:

  1. PARITY FIRST. v2 on ``synthetic_cpg_repo`` must come back bit-identical to
     run 7's reference, or the run is void before it starts.
  2. THE FALSIFICATION TEST, on the fixtures where the dynamic oracle DOES run.
     True edge set = predicted minus the oracle's false edges. The audit
     asserts ``F & D == {}``. A refuter's only defensible error is removing a
     true edge, so this is the one direction that is checkable exactly.
  3. THE MEASUREMENT, on 4 real tarballs and 6 fixtures: how many predicted
     edges are refutable, and what eq. row 17's identifiability condition does
     afterwards.
  4. THE AUDIT OF THE CLAIM, because the claim is a theorem and the loop's
     discipline is that a theorem is run.

Static only on third-party tarballs, as in runs 4-10. The only executions are
against the loop's own fixtures.

Usage:  python3 scripts/run_n13_measurement.py > experiments/run-11-n13.log
"""

from __future__ import annotations

import importlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RUNNER = importlib.import_module("scripts.run_auto_research")
N11RUN = importlib.import_module("scripts.run_n11_measurement")
REF = importlib.import_module("src.11_name_refuter")

REAL = ["pallets/flask", "psf/requests", "tiangolo/sqlmodel", "Textualize/rich"]
FIXTURES = [
    "synthetic_cpg_repo", "synthetic_promo_repo", "synthetic_taint_repo",
    "synthetic_exports_repo", "synthetic_protocol_repo", "synthetic_index_repo",
]
#: Fixtures whose dynamic oracle actually runs. Only these can adjudicate the
#: refuter's SOUNDNESS; the rest are reported without an audit rather than
#: being given a vacuous one.
ORACLE_RUNS = {"synthetic_cpg_repo", "synthetic_promo_repo"}


def audit_repo(repo: str) -> dict:
    """Refutation counts, admissibility, identifiability effect, soundness.

    Every number the node promised is produced here for one corpus, so a reader
    can check the claim against a single row.
    """
    files, _corpus, _meta = RUNNER.load_repo_corpus(repo)
    cpg = RUNNER.CPG_MOD.build_cpg(files)
    predicted = set(cpg.call_edges)

    tok = REF.file_token_sets(files)
    adm = REF.admissible_files(files, tok["unparsed"])
    sym_file = REF.symbol_files(files)
    adm_flags = {
        f: (f not in adm["inadmissible"]) for f in files
    }
    res = REF.refute(predicted, sym_file, tok["tokens"], adm_flags)
    F = {(c, k) for c, k, _ in res["refuted"]}

    row = {
        "repo": repo,
        "is_real_repo": repo in REAL,
        "n_files": len(files),
        "n_symbols_defined": len(sym_file),
        "n_predicted_edges": res["n_predicted"],
        "admissibility": {
            "n_admissible": adm["n_admissible"],
            "n_inadmissible": adm["n_inadmissible"],
            "admissible_fraction": adm["admissible_fraction"],
            "n_unparsed": len(tok["unparsed"]),
            "top_inadmissible_reasons": _reason_hist(adm["inadmissible"]),
        },
        "refutation": {
            "n_refuted": res["n_refuted"],
            "refuted_fraction": res["refuted_fraction"],
            "not_refuted_name_present": res["not_refuted_name_present"],
            "not_refuted_caller_file_inadmissible": res[
                "not_refuted_caller_file_inadmissible"],
            "not_refuted_not_text_faithful": res["not_refuted_not_text_faithful"],
            "not_refuted_caller_file_unknown": res["not_refuted_caller_file_unknown"],
            "sample_refuted": res["refuted"][:12],
        },
    }

    if repo in ORACLE_RUNS:
        oracle = RUNNER.DYN_MOD.run_oracle(files)
        false_edges = {tuple(e) for e in oracle.false_edges(cpg.call_edges)}
        true_edges = predicted - false_edges
        covered = {c for c, _ in true_edges} | set(oracle.invoked)
        row["soundness_audit"] = REF.soundness_audit(F, true_edges)
        row["identifiability"] = REF.identifiability_effect(F, predicted, covered)
        row["oracle_note"] = (
            "executed: true edge set reconstructed as predicted minus the "
            "oracle's false edges, so the audit is exact rather than sampled"
        )
    else:
        row["soundness_audit"] = {
            "status": "UNVALIDATED",
            "reason": (
                "the dynamic oracle does not run on this corpus, so the true edge "
                "set does not exist and the refuter's soundness cannot be checked "
                "HERE. Refuting an edge is always safe in the sense that the edge "
                "is removed from the denominator, but soundness -- that no true "
                "edge was removed -- is only checkable where truth is executed. "
                "Reported as unvalidated rather than as vacuously sound, because "
                "run 10's N12e measured what a vacuous truth looks like."
            ),
        }
    return row


def _reason_hist(inadmissible: dict) -> dict:
    hist: dict = {}
    for reasons in inadmissible.values():
        for r in reasons:
            hist[r] = hist.get(r, 0) + 1
    return dict(sorted(hist.items(), key=lambda kv: -kv[1])[:8])


def main() -> None:
    sc = REF.self_check()
    audits = [audit_repo(r) for r in FIXTURES + REAL]
    real = [a for a in audits if a["is_real_repo"]]
    audited = [a for a in audits if "identifiability" in a]

    out = {
        "variation": "n13_non_executing_adjudicator",
        "metric_def": "unreferenced-domain-v4",
        "max_metric": 80,
        "metric_def_note": (
            "UNCHANGED for the EIGHTH consecutive run. The dead term is UNSCORED, "
            "so harness_score cannot move. What N13 can move is "
            "unadjudicable_edges, which is a DIAGNOSTIC of the standing metric "
            "(eq. row 17) and not a scored term -- so the honest headline is again "
            "that the score did not move, and the run is a theorem plus a filter."
        ),
        "parity": N11RUN.parity(),
        "self_check": sc,
        "audits": audits,
    }

    # --- the claim, audited -------------------------------------------------
    out["claim_audit"] = {
        "claim_as_written_in_the_graph": (
            "an edge (caller, callee) is DEFINITIVELY FALSE if leaf(callee) occurs "
            "nowhere in the caller's body, so unadjudicable_edges can be shrunk on "
            "an untrusted tarball without running the oracle"
        ),
        "fault_1_the_relation_was_substituted": {
            "verdict": "REFUTED as stated; TRUE under a weaker reading",
            "false_reading": (
                "y is invoked at some moment while x is on the stack -- the "
                "relation a call graph denotes"
            ),
            "true_reading": (
                "a CALL instruction, or an attribute access m.y, appears in x's own "
                "code object"
            ),
            "counterexample": "def x(h): return h()   # in x.py\ndef h(): return y()",
            "measured": (
                "'y' in tokens(h.py) and 'y' not in tokens(x.py), asserted in "
                "src/11_name_refuter.py::self_check as fault1_dynamic_reading_refuted"
            ),
            "consequence": (
                "the node's rationale silently substituted the second reading for "
                "the first. This is the THIRD instance of the loop's own recorded "
                "failure mode -- a claim proved for a chosen hypothesis class and "
                "published as a property of the problem (eq. rows 30 and 32)."
            ),
        },
        "fault_2_the_loops_own_repair_manufactures_the_counterexample": {
            "verdict": "REFUTED under BOTH readings, by eq. row 6",
            "mechanism": (
                "row 6 normalised a class-instantiation edge to Cls.__init__ because "
                "CPython calls __init__ directly. 'return K()' is a real, direct "
                "dispatch whose callee leaf '__init__' appears nowhere in the "
                "caller's file, so the un-guarded refuter certifies a FALSE edge."
            ),
            "asserted": "fault2_refuted_without_a2 and fault2_a2_blocks_it, both true",
            "wrong_first_counterexample": (
                "the loop's first counterexample was an ALIASED IMPORT, 'from M "
                "import y as a; a()'. It is NOT a counterexample: the import "
                "statement spells y, so y is in T(C_x) and the lemma holds. A "
                "refutation resting on a counterexample that does not refute is "
                "worse than none, and the first cut of the module asserted one. "
                "alias_bindings() is kept as a diagnostic so the error stays auditable."
            ),
            "a2_is_coarse": (
                "text_faithful() excludes resolver-supplied leaves only. A tighter "
                "test needs the resolver's raw text per edge, which the CPG does not "
                "record, and inferring it from the dotted symbol is the string "
                "surgery behind run 7's defect (ii)."
            ),
        },
        "surviving_rule": (
            "admissible(x, y) := A1(no dynamic-name-construction site in C_x) and "
            "A2(y is text-faithful). Then leaf(y) not in T(C_x) implies (x, y) is "
            "definitively false. Both conditions are CHECKED, both are refusal "
            "triggers, and both over-refuse: a false positive costs a refutation, a "
            "false negative costs soundness."
        ),
        "why_this_is_not_run_7s_killed_manifest": (
            "run 7's protocol manifest was an OPEN list of names, so it vetoed only "
            "what it listed and failed UNSOUNDLY (precision 0.0, 1 false positive). "
            "These sets are refusal triggers, so a wrong entry makes the analysis "
            "refuse more, never less. The direction of every error is opposite, and "
            "that is the whole difference."
        ),
        "prior_art_status": "PENDING -- see the run's own note; all three literature "
                            "sub-agents died on provider quota this iteration "
                            "(Gemini free-tier 429, OpenRouter free-model daily cap)",
    }

    # --- what it is worth ---------------------------------------------------
    total_pred = sum(a["n_predicted_edges"] for a in real)
    total_ref = sum(a["refutation"]["n_refuted"] for a in real)
    out["n13_verdict"] = {
        "soundness_audit_on_executed_fixtures": {
            a["repo"]: a["soundness_audit"]["sound"] for a in audited
        },
        "any_soundness_violation": any(
            a["soundness_audit"]["sound"] is not True for a in audited
        ),
        "soundness_audited_on": [a["repo"] for a in audited],
        "soundness_UNVALIDATED_on": [a["repo"] for a in audits
                                     if a["soundness_audit"].get("status") ==
                                     "UNVALIDATED"],
        "n_predicted_edges_real_repos": total_pred,
        "n_refuted_real_repos": total_ref,
        "refuted_fraction_real_repos": (
            round(total_ref / total_pred, 6) if total_pred else None
        ),
        "identifiability_achieved_anywhere": any(
            a["identifiability"]["identifiable_after"] for a in audited
        ),
        "unadjudicable_before_after": {
            a["repo"]: [a["identifiability"]["n_unadjudicable_before"],
                        a["identifiability"]["n_unadjudicable_after"]]
            for a in audited
        },
        "the_measured_reason_it_is_worth_little": (
            "F is empty on the CPG's own edges, and that is structural rather than "
            "unlucky: the CPG adds (sym, callee) only where a resolved ast.Call "
            "sits in sym's body, so leaf(callee) is already a token of that body. A "
            "necessary condition on an edge that was DERIVED from a call site is "
            "almost always already satisfied. The refuter can only bite on edges "
            "predicted WITHOUT a call site in the caller's body, which is run 3's "
            "name-promotion family (mode B) -- and those were never scored on a real "
            "repo either, because the structural term has been withheld there since "
            "run 4."
        ),
        "reported_against_interest": [
            "the node's stated purpose was to unblock N8, and it does not: "
            "identifiable_after is still False everywhere, because a refuter shrinks "
            "the unadjudicable set without emptying it. N8 stays blocked, now with "
            "the mechanism of the block measured rather than asserted.",
            "A2's exclusion of __init__ edges removes exactly the edges a call graph "
            "care about most, so the filter is weakest where call graphs are most "
            "used. This is the price of soundness and it is not tunable away.",
            "soundness is checkable on 2 of 10 corpora. The other 8 are reported "
            "UNVALIDATED, not vacuously sound -- run 10's N12e is the precedent for "
            "what happens when a vacuous truth is published as a result.",
        ],
        "monotonicity": sc["monotonicity"],
    }
    print(json.dumps([out], indent=1))


if __name__ == "__main__":
    main()
