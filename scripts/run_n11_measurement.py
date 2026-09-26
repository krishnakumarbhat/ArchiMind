"""Run 8 / N11 measurement: derive the bound, state the dichotomy, size the interface.

Replaces run 7's hardcoded ``"max_accuracy_on_pair": 0.5`` with a number computed by
exhaustive enumeration, states what that number does and does not license, and
measures -- on all nine corpora, four of them real tarballs -- how much of the
gate's certified output is not a per-symbol verdict at all.

Static only on third-party tarballs, exactly as in runs 4-7: the dynamic oracle
executes code and never runs on an untrusted repository. The one execution here is
against the loop's own fixture and its own out-of-corpus driver.

Usage:  python3 scripts/run_n11_measurement.py > experiments/run-8-n11.log
"""

from __future__ import annotations

import importlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RUNNER = importlib.import_module("scripts.run_auto_research")
DOMAIN = importlib.import_module("src.04_symbol_domain")
EXPORT = importlib.import_module("src.05_export_boundary")
PROTO = importlib.import_module("src.06_protocol_driver")
IC = importlib.import_module("src.07_import_closure")
N11 = importlib.import_module("src.08_interface_index")
N10 = importlib.import_module("scripts.run_n10_measurement")

REAL = ["pallets/flask", "psf/requests", "tiangolo/sqlmodel", "Textualize/rich"]
FIXTURES = [
    "synthetic_cpg_repo", "synthetic_promo_repo", "synthetic_taint_repo",
    "synthetic_exports_repo", "synthetic_protocol_repo", "synthetic_index_repo",
]
# Run 7's reference row on the parity fixture. Every one of these is a QUALITY
# quantity and must be bit-identical; only the resource term may move.
PARITY_REFERENCE = {
    "struct_precision_dyn": 1.0, "struct_recall_dyn": 0.5, "dead_code_acc": 0.3333,
    "cpg_resolution_rate": 0.5, "blast_latency_ms": 0.51, "struct_false_edges": [],
}


def build_index_fixture(path="experiments/fixtures/synthetic_index_repo"):
    """Delegate to the runner, which owns every other fixture builder."""
    return RUNNER.build_index_fixture(path)


def parity():
    """The v2 row on the parity fixture, checked against run 7's reference.

    DEFECT AND ITS WRONG DIAGNOSIS, both recorded because the second is the more
    dangerous. The first version of this function read the metrics out of
    ``row["dyn"]``. ``run_one`` does not nest them: it ends with ``out.update(dyn)``,
    so the row is FLAT and ``row.get("dyn", {})`` returns ``{}``. All six quality
    fields came back ``null``, ``identical_to_run7`` read ``False``, and the diff
    block printed run 7's own values against ``None`` -- a fabricated quality
    regression out of a pure key lookup.

    The first attempt to fix it blamed ``run_v3``, which really does return
    ``status: unvalidated`` on this fixture (fold B observes no dispatches, so its
    protocol is undefined). That diagnosis was wrong and was never executed: this
    function never called ``run_v3``. A plausible story attached to a defect that
    was not the cause is worse than no story, because the next iteration inherits
    it and stops looking. The repair is to read the flat row, and the assertion
    below is what makes the two cases distinguishable from now on.
    """
    row = RUNNER.run_one("v2_treesitter_cpg", "synthetic_cpg_repo")
    assert "dyn" not in row, (
        "run_one has started nesting its metrics; parity() must read row['dyn'] "
        "and this docstring is the thing that is now wrong"
    )
    dyn = row
    got = {
        "struct_precision_dyn": dyn.get("struct_precision_dyn"),
        "struct_recall_dyn": dyn.get("struct_recall_dyn"),
        "dead_code_acc": dyn.get("dead_code_acc"),
        "cpg_resolution_rate": dyn.get("cpg_resolution_rate"),
        "blast_latency_ms": dyn.get("blast_latency_ms"),
        "struct_false_edges": dyn.get("struct_false_edges"),
    }
    absent = sorted(k for k, v in got.items() if v is None)
    assert not absent, (
        f"parity fields absent from the row: {absent}. A null is a missing metric, "
        "not a changed one -- report it as an instrument defect, never as a diff."
    )
    diffs = {k: {"run7": PARITY_REFERENCE[k], "run8": got[k]}
             for k in PARITY_REFERENCE if got[k] != PARITY_REFERENCE[k]}
    return {
        "fixture": "synthetic_cpg_repo",
        "source": "run_one('v2_treesitter_cpg', 'synthetic_cpg_repo')",
        "measured": got,
        "identical_to_run7": not diffs,
        "diffs": diffs,
        "composite": row.get("harness_score"),
        "composite_runs_2_to_7": 86.23,
        "note": (
            "every scored QUALITY quantity must be bit-identical. blast_latency_ms "
            "and peak_ram_mb are the resource terms and are the only fields allowed "
            "to move; the composite delta is attributed to them alone."
        ),
    }


def index_fixture_measurement():
    """The bound, the dichotomy, the control and the interface cost, on one fixture.

    Truth is EXECUTED, not written down: the driver's sentinels say which four
    methods it reached.
    """
    repo = "synthetic_index_repo"
    build_index_fixture()
    files, corpus, meta = RUNNER.load_repo_corpus(repo)
    probe = PROTO.fixture_driver_probe(
        os.path.join(RUNNER._fixture_dir(repo)),
        "experiments/fixtures/synthetic_index_driver",
    )
    reached = set(probe.get("reached_sentinels", []))

    cpg = RUNNER.CPG_MOD.build_cpg(files)
    dead = cpg.dead_symbols(dunder_exempt=True)
    counts = DOMAIN.token_name_counts(corpus.values())
    wit = IC.out_of_corpus_bases(files, corpus)

    class_methods = sorted(s for s in dead if s.startswith("alpha.T."))
    lasso = {s: (s not in reached) for s in class_methods}  # True == DEAD
    feats = N11.features_for(class_methods, dead, counts, corpus, wit)
    classes = N11.e_classes(feats)

    conj = N11.conjunctive_gates()
    ex4 = N11.exhaustive_gates(4)
    acc_conj = N11.max_accuracy_over_gates(classes, lasso, conj, feats)
    acc_ex = N11.max_accuracy_over_gates(classes, lasso, ex4, feats)
    front = N11.pareto_frontier(classes, lasso, conj, feats)
    ctrl = N11.interface_bit_control(classes, lasso, conj, feats)
    nu = N11.nu_index(classes, lasso)

    # What the loop's own gates actually do on this fixture.
    run5 = DOMAIN.certify_unreferenced(dead, counts)
    run7 = IC.certify_dead_base_witness(dead, counts, wit, EXPORT.externally_driven(dead))
    manifest = PROTO.manifest_withheld(dead)
    with_manifest = IC.certify_dead_base_witness(dead, counts, wit, manifest)

    def acc_of(certified):
        fp = sorted(s for s in certified if s in lasso and not lasso[s])
        tp = sorted(s for s in certified if s in lasso and lasso[s])
        n = sum(1 for s in class_methods if s in lasso)
        return {
            "certified": sorted(certified), "n_certified": len(certified),
            "false_positives": fp, "n_false_positives": len(fp),
            "true_positives": tp, "n_true_positives": len(tp),
            "precision": round(len(tp) / len(certified), 4) if certified else None,
            "recall": round(len(tp) / sum(1 for v in lasso.values() if v), 4),
            "accuracy": round((len(tp) + (n - len(certified))) / n, 4) if n else None,
        }

    manifest_names = PROTO.PROTOCOL_NAMES
    # Does the killed manifest land on the law? The curve predicts the accuracy of
    # withholding j of the |L| live names, so run 7's measured 0.875 is a
    # PREDICTION rather than a number that happened to come out.
    live_order = sorted(s for s in class_methods if s in lasso and not lasso[s])
    curve = N11.interface_value_curve(
        classes, lasso, feats, live_order, N11.conjunctive_gates(N11.N_FEATURES + 1))
    m = acc_of(with_manifest)
    j = len([s for s in live_order if s.rsplit(".", 1)[-1] in manifest_names])
    return {
        "repo": repo,
        "driver_status": probe.get("status"),
        "driver_protocol_tuple": probe.get("protocol_tuple"),
        "n_reached_by_execution": len(reached),
        "reached_symbols": sorted(reached),
        "liveness_derivation": "EXECUTED: the sentinel set returned by the out-of-corpus driver",
        "n_class_methods": len(class_methods),
        "n_predicted_dead": len(dead),
        "n_e_classes": nu["n_classes"],
        "n_mixed_classes": nu["n_mixed_classes"],
        "class_sizes": [c["size"] for c in nu["per_class"]],
        "mixed_class_split": [
            {"dead": c["dead"], "live": c["live"]} for c in nu["per_class"] if c["mixed"]
        ],
        "nu": nu["nu"],
        "derived_bound": nu["max_accuracy_on_any_mixed_class"],
        "bound_is_derived_not_literal": True,
        "max_accuracy_conjunctive": acc_conj,
        "max_accuracy_all_gates_4_features": acc_ex,
        "zero_variance_across_gates": (
            acc_conj["max_accuracy"] == acc_conj["min_accuracy"]
            and acc_ex["max_accuracy"] == acc_ex["min_accuracy"]
        ),
        "pareto_frontier": front,
        "dichotomy_is_exact": front["is_binary_dichotomy"] and front["sound_points_all_zero"],
        "interface_bit_control": ctrl,
        "stated_claims": N11.stated_claims(),
        "interface_value_curve": curve,
        "n10_manifest_lands_on_the_law": {
            "correct_bits_supplied_by_manifest": j,
            "law_predicts_accuracy": curve["rows"][j]["agreement_closed_form"],
            "measured_accuracy": m["accuracy"],
            "prediction_holds": abs(m["accuracy"] - curve["rows"][j]["agreement_closed_form"]) < 1e-9,
            "curve_it_lands_on": "agreement",
            "sound_curve_value_at_the_same_j": curve["rows"][j]["sound_max_accuracy"],
            "why_it_matters": (
                "run 7 recorded 0.875 for the manifest with no law behind it. Here "
                "0.875 is PREDICTED from the number of correct bits it supplies, so "
                "the number is explained rather than merely observed -- and the "
                "unexplained part (the one missed name) is exactly the residual. It "
                "lands on the AGREEMENT curve, not the sound one, which is the whole "
                "point: the manifest is an unsound gate and 0.875 is its agreement "
                "accuracy, so the law predicts it correctly while licensing nothing."
            ),
        },
        "invariance_in_m": N11.invariance_in_m(),
        "invariance_single_class": N11.invariance_single_class(),
        "interface_cost_arbitrary_bit": N11.interface_cost_bits(classes, lasso)["arbitrary_spec_bits"],
        "interface_cost_allowlist": N11.interface_cost_bits(
            classes, lasso, allowlist={s.rsplit(".", 1)[-1] for s in reached}
        ),
        "n10_manifest_allowlist_cost_bits": N11.interface_cost_bits(
            classes, lasso, allowlist=manifest_names
        ),
        "n10_manifest_covers_fixture": manifest_names >= reached,
        "loop_gates_on_this_fixture": {
            "run5_unreferenced": acc_of(run5),
            "run6_export_boundary": acc_of(EXPORT.certify_dead_within_corpus(
                dead, counts, EXPORT.star_import_witnesses(corpus))),
            "run7_base_witness": acc_of(run7),
            "run7_plus_n10_manifest": acc_of(with_manifest),
        },
        "dichotomy_observed": {
            "every_gate_that_certifies_anything_here_is_unsound": all(
                v["n_false_positives"] == v["n_certified"]
                for k, v in {
                    "run5": acc_of(run5), "run7": acc_of(run7),
                    "run7_manifest": acc_of(with_manifest),
                }.items()
            ),
            "the_sound_option_certifies": 0,
        },
        "ambiguity_report": N11.ambiguity_report(run7, feats, demonstrated_live=reached),
    }


def demonstrated_live_symbols(certified):
    """Corpus symbols an EXECUTED real framework actually dispatched to.

    Derived from the probes, not from a hand-written list: for each executed probe,
    a dispatched name is matched to the certified symbol with that leaf name. Run 7
    recorded the same four residuals by hand; deriving them keeps the number honest
    if the probes change.
    """
    found = set()
    for _, p in PROTO.real_framework_probes().items():
        if p.get("status") != "executed":
            continue
        for name in p.get("dispatched", []):
            found |= {s for s in certified if s.rsplit(".", 1)[-1] == name}
    return found


def corpus_ambiguity(repo):
    """How much of this repo's certified output is not a per-symbol verdict.

    Needs no ground truth, so it runs on the four real tarballs. This is a LOWER
    BOUND on the external interface the corpus cannot supply.
    """
    files, corpus, meta = RUNNER.load_repo_corpus(repo)
    cpg = RUNNER.CPG_MOD.build_cpg(files)
    dead = cpg.dead_symbols(dunder_exempt=True)
    counts = DOMAIN.token_name_counts(corpus.values())
    wit = IC.out_of_corpus_bases(files, corpus)
    certified = IC.certify_dead_base_witness(
        dead, counts, wit, EXPORT.externally_driven(dead))
    feats = N11.features_for(dead, dead, counts, corpus, wit)
    live = demonstrated_live_symbols(certified)
    rep = N11.ambiguity_report(certified, feats, demonstrated_live=live)
    rep["repo"] = repo
    rep["n_predicted_dead"] = len(dead)
    ecls = N11.e_classes(feats)
    rep["n_e_classes_over_dead_set"] = len(ecls)
    # DEFECT (iv): the per-class declaration is NOT worth zero, because the class
    # partition splits the E-class partition. Needs no ground truth, so it runs here
    # on all nine corpora. `enclosing_class` is the same resolution the evidence
    # vector uses, so the map cannot disagree with the features it explains.
    classes_of = {s: (IC.enclosing_class(s, corpus) or "<none>") for s in feats}
    ref = N11.partition_refinement(ecls, classes_of)
    rep["e_class_split_by_python_class"] = {
        k: v for k, v in ref.items() if k != "split_e_classes"
    }
    rep["e_class_split_by_python_class"]["largest_n_classes_in_one_e_class"] = max(
        (x["n_distinct_python_classes"] for x in ref["split_e_classes"]), default=0)
    rep["certification_rate"] = round(len(certified) / len(dead), 4) if dead else None
    rep["is_real_repo"] = repo in REAL
    rep["ground_truth_note"] = (
        "no ground truth on a real repo, so this is a bound on the AMBIGUITY of the "
        "output, not an accuracy claim. The direction is conservative: a class is "
        "counted ambiguous whenever it has more than one member, whatever the truth."
    )
    return rep


def main():
    out = {
        "variation": "n11_interface_index_dichotomy",
        "metric_def": "unreferenced-domain-v4",
        "max_metric": 80,
        "metric_def_note": (
            "UNCHANGED for the fifth consecutive run. The dead term is UNSCORED, so "
            "harness_score cannot move; the deliverable is the DERIVED bound, the "
            "stated dichotomy and the measured interface size."
        ),
        "parity": parity(),
        "index_fixture": index_fixture_measurement(),
        "invariance_in_m": N11.invariance_in_m(),
        "invariance_single_class": N11.invariance_single_class(),
        "corpus_ambiguity": [corpus_ambiguity(r) for r in FIXTURES + REAL],
    }
    # DEFECT (iv) adjudication, at the top level so the retraction cannot be read
    # without its refutation. Run 8 claimed a class-level declaration is worth
    # exactly zero. It is not, and the loop's own data says so on every real repo.
    splits = [c["e_class_split_by_python_class"] for c in out["corpus_ambiguity"]]
    real_splits = [s for c, s in zip(out["corpus_ambiguity"], splits) if c["is_real_repo"]]
    out["n11b_class_level_declaration_retraction"] = {
        "retracted_claim": (
            "a class-level declaration (class T(Protocol), @runtime_checkable, a "
            "written base, __all__, a docstring) is worth EXACTLY ZERO bits, because "
            "it is constant on the class and hence constant on the class's evidence"
        ),
        "fault_1_mislabelled_arm": (
            "the control appended ONE value to EVERY symbol, so it measured a GLOBAL "
            "constant and reported it under the name class_level"
        ),
        "fault_2_inverted_predicate": (
            "the first replacement counted classes SPANNING two E-classes, which buys "
            "nothing, instead of E-classes SPLIT across two classes, which is the "
            "only way a per-class value separates symbols. It reported 4/6/6/5 and "
            "would have appeared to SUPPORT the retracted claim"
        ),
        "corrected_statement": (
            "a per-class declaration buys lift exactly when it splits an E-class; the "
            "lift is zero iff the class partition coarsens the E-class partition"
        ),
        "n_e_classes_split_real": [s["n_split_e_classes"] for s in real_splits],
        "n_e_classes_total_real": [s["n_e_classes"] for s in real_splits],
        "split_fraction_real": [s["split_fraction"] for s in real_splits],
        "predicted_dead_symbols_in_a_split_e_class_real": [
            s["n_symbols_in_split_e_classes"] for s in real_splits],
        "largest_n_classes_in_one_e_class_real": [
            s["largest_n_classes_in_one_e_class"] for s in real_splits],
        "any_real_repo_fully_unsplit": all(
            s["class_partition_coarsens_e_partition"] for s in real_splits),
        "verdict": "REFUTED on all four real repos; the retracted zero is withdrawn",
        "corroboration_from_run7": (
            "run 7's inheritance witness IS a per-class declaration and removed 9 "
            "real-repo certificates, which a globally constant feature cannot do"
        ),
        "p4_verdict_prior_art": "PRIOR_ART_STANDARD (a classifier is constant on a fibre)",
        "p3_verdict_prior_art": "NOVEL-but-taxonomic, literature link UNVERIFIED",
        "novelty_score": 22,
    }
    real = [c for c in out["corpus_ambiguity"] if c["is_real_repo"]]
    out["real_repo_ambiguity_summary"] = {
        "n_real_repos": len(real),
        "total_certified": sum(c["n_certified"] for c in real),
        "total_certified_not_per_symbol": sum(
            c["n_certified_in_multi_symbol_class"] for c in real),
        "total_interface_lower_bound_bits": sum(c["interface_lower_bound_bits"] for c in real),
        "total_demonstrated_live_bits": sum(
            c["interface_lower_bound_bits_demonstrated"] for c in real),
        "per_repo": [
            {"repo": c["repo"], "certified": c["n_certified"],
             "not_per_symbol": c["n_certified_in_multi_symbol_class"],
             "fraction": c["fraction_not_per_symbol"],
             "bits": c["interface_lower_bound_bits"]}
            for c in real
        ],
    }
    print(json.dumps([out], indent=1))


if __name__ == "__main__":
    main()
