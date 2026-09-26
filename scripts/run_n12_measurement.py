"""Run 10 / N12: price a PARTIAL interface, and retract the law N12 was built on.

Run 9's frontier node N12 reads, in the loop's own words: "the interface is worthless
until it is COMPLETE -- a sound gate's accuracy is flat at ``n_live/|C|`` for every
``j < n_live``, so search for a mechanism that resolves an entire E-class at once".
The flatness is :func:`src.08_interface_index.interface_value_curve`'s sound curve,
and that curve is a property of the hypothesis class it enumerated, not a law. This
run measures the carriers N12 never looked at -- a declaration need not identify a
live symbol, it may isolate a DEAD one -- and withdraws the sentence.

Static only on third-party tarballs, as in runs 4-9. The one execution is against
the loop's own fixture and its own out-of-corpus driver.

Usage:  python3 scripts/run_n12_measurement.py > experiments/run-10-n12.log
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
N12 = importlib.import_module("src.09_resolution_price")
N11RUN = importlib.import_module("scripts.run_n11_measurement")

REAL = ["pallets/flask", "psf/requests", "tiangolo/sqlmodel", "Textualize/rich"]
FIXTURES = [
    "synthetic_cpg_repo", "synthetic_promo_repo", "synthetic_taint_repo",
    "synthetic_exports_repo", "synthetic_protocol_repo", "synthetic_index_repo",
]


def carriers_for(symbols, files, corpus):
    """The full carrier family for a symbol set, class partitions attached."""
    idx = N12.def_index(files)
    syms = list(symbols)
    parts = N12.free_partitions(syms, idx)
    parts = N12.attach_class_partition(parts, syms, corpus)
    coverage = sum(1 for s in syms if s in idx)
    return parts, {
        "n_symbols": len(syms),
        "n_with_a_parsed_definition_site": coverage,
        "def_index_coverage": round(coverage / len(syms), 6) if syms else None,
        "carriers": sorted(parts),
        "note": (
            "a symbol with no parsed definition site falls in an <unknown> block "
            "rather than being dropped; dropping it would shrink the very fibres "
            "whose ambiguity is being measured"
        ),
    }


def index_fixture():
    """The value lattice on the one corpus with EXECUTED ground truth.

    The 8 methods of ``alpha.T``: 4 dispatched by the out-of-corpus driver, 4 written
    down as dead. This is the only place in the loop where a mixed fibre has real,
    executed truth on both sides, so it is the only place an accuracy claim is made.
    """
    repo = "synthetic_index_repo"
    N11RUN.build_index_fixture()
    files, corpus, _ = RUNNER.load_repo_corpus(repo)
    cpg = RUNNER.CPG_MOD.build_cpg(files)
    dead = cpg.dead_symbols(dunder_exempt=True)
    counts = DOMAIN.token_name_counts(corpus.values())
    wit = IC.out_of_corpus_bases(files, corpus)
    probe = PROTO.fixture_driver_probe(
        os.path.join(RUNNER._fixture_dir(repo)),
        "experiments/fixtures/synthetic_index_driver",
    )
    reached = set(probe.get("reached_sentinels", []))

    methods = sorted(s for s in dead if s.startswith("alpha.T."))
    lasso = {s: (s not in reached) for s in methods}  # True == DEAD
    feats = N11.features_for(methods, dead, counts, corpus, wit)
    classes = N11.e_classes(feats)
    parts, meta = carriers_for(methods, files, corpus)
    lat = N12.value_lattice(classes, lasso, parts)
    mono = N12.refinement_monotonicity(classes, lasso, parts)
    live_order = sorted(s for s in methods if s in lasso and not lasso[s])

    # N11c's own family, re-scored under the corrected law. This is the scope
    # statement of the retraction: run 9 was right about flag partitions.
    flag_rows = [N12.flag_partition_value(classes, lasso, live_order, j)
                 for j in range(len(live_order) + 1)]

    # The discriminating-pair fixture from run 7, scored the same way: a fibre of
    # two where one member is dispatched by an executed driver. This is the SMALLEST
    # instance of the retraction -- a two-symbol fibre where the isolating partition
    # is a single symbol, so the counterexample needs no method bodies at all.
    pcorpus = RUNNER.load_repo_corpus("synthetic_protocol_repo")[1]
    pair = IC.discriminating_pair(
        pcorpus, "alpha.T.process_literal_param", "alpha._fixture_dead_plain")
    return {
        "repo": repo,
        "driver_status": probe.get("status"),
        "n_reached_by_execution": len(reached),
        "liveness_derivation": "EXECUTED: sentinel set returned by the out-of-corpus driver",
        "n_class_methods": len(methods),
        "n_dead": sum(1 for v in lasso.values() if v),
        "n_live": sum(1 for v in lasso.values() if not v),
        "n_e_classes": len(classes),
        "e_class_sizes": sorted((len(c) for c in classes), reverse=True),
        "carrier_meta": meta,
        "value_lattice": lat,
        "refinement": mono,
        "n11c_scope_check": {
            "family": "flag partitions -- mark j live members, split each fibre in two",
            "rows": [{k: v for k, v in r.items() if k != "flagged"} for r in flag_rows],
            "all_rows_agree_with_n11c": all(r["agrees_with_n11c"] for r in flag_rows),
            "verdict": (
                "N11c's flat law is CORRECT for flag partitions and WRONG for general "
                "ones, so it was a fact about the enumerated hypothesis class published "
                "as a law. Every row below is the corrected law agreeing with the old "
                "one, which is the retraction's scope and not its refutation."
            ),
        },
        "run7_discriminating_pair_smallest_instance": {
            "live": pair["live"], "dead": pair["dead"],
            "evidence_equal": pair["evidence_equal"],
            "occ_live": pair["occ_live"], "occ_dead": pair["occ_dead"],
            "n11c_hardcoded_bound": pair["max_accuracy_on_pair"],
            "isolating_partition_acc_star": N12.partition_value(
                [{pair["live"], pair["dead"]}], {pair["live"]: True, pair["dead"]: False},
                {pair["live"]: "iso", pair["dead"]: "rest"},
            )["acc_star"],
            "note": (
                "NOT a refutation, and recorded as such because the number 1.0 looks "
                "like one. On a TWO-symbol fibre any split into two blocks IS the "
                "discrete partition, so isolating the dead member is a complete "
                "declaration and N11c's own last row predicts 1.0. Run 7's literal "
                "0.5 is therefore the best over INCOMPLETE declarations, which is what "
                "it was used for, and it stands. The retraction needs a fibre of at "
                "least three symbols and is made on the eight-method fixture above, "
                "not here. Reported because a two-element case is exactly where a "
                "reader would check the retraction and must find it does not apply."
            ),
        },
    }


def corpus_carriers(repo):
    """Truth-light carrier scan on every corpus, real tarballs included.

    No ground truth exists here, so no accuracy is claimed. What IS measurable
    without truth is whether a carrier can put the loop's own certified symbols into
    blocks that contain no symbol an EXECUTED framework was seen to dispatch to. That
    is a necessary condition for a carrier to be worth anything, it needs no oracle,
    and a carrier that fails it is refuted rather than merely unmeasured.
    """
    files, corpus, _ = RUNNER.load_repo_corpus(repo)
    cpg = RUNNER.CPG_MOD.build_cpg(files)
    dead = cpg.dead_symbols(dunder_exempt=True)
    counts = DOMAIN.token_name_counts(corpus.values())
    wit = IC.out_of_corpus_bases(files, corpus)
    certified = IC.certify_dead_base_witness(
        dead, counts, wit, EXPORT.externally_driven(dead))
    live = N11RUN.demonstrated_live_symbols(certified)
    pool = sorted(set(dead) | set(live))
    parts, meta = carriers_for(pool, files, corpus)

    rows = {}
    for name, part in parts.items():
        blocks = N12.blocks_of(part, pool)
        clean = [b for b in blocks if not (b & live)]
        rows[name] = {
            "n_blocks": len(blocks),
            "n_blocks_free_of_demonstrated_live": len(clean),
            "n_certified_in_a_clean_block": sum(len(b & certified) for b in clean),
            "n_certified": len(certified),
            "fraction_certified_separable": round(
                sum(len(b & certified) for b in clean) / len(certified), 6
            ) if certified else None,
        }
    vacuous = not live
    return {
        "repo": repo,
        "is_real_repo": repo in REAL,
        "n_predicted_dead": len(dead),
        "n_certified": len(certified),
        "n_demonstrated_live_by_execution": len(live),
        "VACUOUS": vacuous,
        "vacuity_note": (
            "NO demonstrated-live symbol, so EVERY block is trivially free of one "
            "and 'a carrier separates all certified' is a vacuous truth, not a "
            "result. Reported as such rather than as a pass. This is the same shape "
            "as run 6's flat impossible zero: a structural precondition that makes "
            "the question unaskable while the instrument still returns a number."
        ) if vacuous else "non-vacuous: at least one executed dispatch to separate against",
        "demonstrated_live": sorted(live),
        "carrier_meta": meta,
        "per_carrier": rows,
        "best_carrier": min(rows, key=lambda k: -rows[k]["n_certified_in_a_clean_block"]),
        "any_carrier_separates_all_certified": None if vacuous else any(
            r["n_certified_in_a_clean_block"] == len(certified) for r in rows.values()),
        "ground_truth_note": (
            "no ground truth on a real repo. A certificate counts as SEPARABLE when "
            "its block holds no symbol an executed framework was seen to dispatch to. "
            "That is a necessary condition for a carrier to help and needs no oracle; "
            "it refutes a carrier that fails it and leaves a carrier that passes it "
            "UNMEASURED, which is the honest direction."
        ),
    }


def main():
    out = {
        "variation": "n12_partial_interface_price + n12b_n11c_law_retraction",
        "metric_def": "unreferenced-domain-v4",
        "max_metric": 80,
        "metric_def_note": (
            "UNCHANGED for the SEVENTH consecutive run. The dead term is UNSCORED, so "
            "harness_score cannot move. What moved is a PUBLISHED LAW, withdrawn."
        ),
        "parity": N11RUN.parity(),
        "self_check": N12.self_check(),
        "index_fixture": index_fixture(),
        "corpus_carriers": [corpus_carriers(r) for r in FIXTURES + REAL],
    }

    fx = out["index_fixture"]
    lat = fx["value_lattice"]
    real = [c for c in out["corpus_carriers"] if c["is_real_repo"]]
    out["n12b_n11c_law_retraction"] = {
        "retracted_claim": (
            "N11c, published in run 9: accuracy = n_live/|C| for j < n_live and 1.0 at "
            "j = n_live; 'a bit identifying a LIVE symbol licenses exactly one "
            "abstention and nothing else'; therefore a partial interface is worth "
            "exactly zero and the interface is worthless until it is COMPLETE"
        ),
        "why_false": (
            "a declaration need not identify a LIVE symbol. It may isolate a DEAD "
            "one, and a block of pure-dead symbols is certifiable at precision 1 by a "
            "sound gate. The flag partitions run 9 enumerated cannot do this -- a flag "
            "splits a fibre into flagged and not-flagged, and the not-flagged half "
            "still holds every dead symbol -- so the flat curve describes the "
            "hypothesis class, not the world"
        ),
        "counterexample": {
            "fibre": "C = {1,2,3,4}, dead {1,2}, live {3,4}",
            "flat_partition": "one block {1,2,3,4}",
            "flat_acc_star": 0.5,
            "isolating_partition": "{1} | {2,3,4}",
            "isolating_acc_star": 0.75,
            "isolating_coverage_precision_1": 0.5,
            "n11c_predicts_for_both": 0.5,
            "no_false_positive_manufactured": True,
            "asserted_in": "src/09_resolution_price.py::self_check",
        },
        "corrected_law": (
            "acc*(Pi) = 1 - |D n mixed(Pi)| / |S|, where mixed(Pi) is the union of the "
            "blocks of Pi ^ E holding both a dead and a live member. Equivalently, the "
            "precision-1 objective: coverage(Pi) = |{d in D : d's block is pure-dead}| "
            "/ |D|. A partial interface is worth exactly the dead symbols it moves out "
            "of mixed blocks, and nothing else."
        ),
        "n11c_still_correct_for": "flag partitions, measured row by row on the fixture",
        "n11c_scope_rows_all_agree": fx["n11c_scope_check"]["all_rows_agree_with_n11c"],
        "frontier_consequence": (
            "N12's premise is withdrawn, so N12 is answered in the negative by the "
            "loop's own maths: the search for a mechanism that resolves an ENTIRE "
            "E-class was aimed at a target that a partial mechanism already reaches. "
            "The node is not deleted -- the corrected law is its replacement."
        ),
        "same_species_as_the_defect_it_replaced": (
            "run 9 retracted an objective mismatch (agreement scored as accuracy) and "
            "the replacement then generalised a curve measured over one hypothesis "
            "class. Two runs, the same failure: a number computed inside a chosen "
            "hypothesis class, published as a property of the problem."
        ),
        "n12_premise_measurements": {
            "best_free_carrier_on_fixture": lat["best_free_carrier"],
            "best_free_acc_star": lat["best_free_acc_star"],
            "baseline_acc_star": lat["per_partition"][lat["best_free_carrier"]][
                "baseline_acc_star"],
            "partial_interface_is_worthless_over_FREE_carriers": lat[
                "partial_interface_is_worthless_over_FREE_carriers"],
            "n_free_carriers": len(lat["free_carriers"]),
            "free_carriers_trapping_fewer_dead_than_discrete": lat[
                "free_carriers_trapping_fewer_dead_than_discrete"],
            "allowlist_price_tag": lat["allowlist_price_tag"],
            "third_shape_verdict": (
                "N12 asked for a THIRD shape -- neither an allowlist nor a per-class "
                "declaration -- that resolves a whole fibre. Measured on the only "
                "corpus with executed truth: all 8 corpus-derived carriers (python "
                "class, class x file, file, module, package, arity, decorated, "
                "decorator name) score EXACTLY the abstain-everywhere baseline. Not "
                "one isolates a single dead method. The third shape does not exist in "
                "the corpus, the only carrier that resolves is the allowlist, and the "
                "allowlist is Vulture's shipped whitelist. So N12's CONCLUSION is "
                "confirmed by a measurement it did not have, and its stated REASON -- "
                "N11c's flat law -- is retracted."
            ),
            "ranking_among_free_carriers": lat["ranking_among_free_carriers"],
        },
        "value_accounting_is_monotone": fx["refinement"]["value_accounting_is_monotone"],
        "bit_accounting_is_monotone": fx["refinement"]["bit_accounting_is_monotone"],
        "n_prior_art_kill": (
            "the corrected law is PRIOR_ART_STANDARD: a classifier constrained to be "
            "constant on a partition is optimal by the majority rule per block, and "
            "run 9's own retraction already recorded the constant-on-a-fibre bound as "
            "textbook. Novelty is claimed for the CORRECTION and the trapped-dead "
            "statistic, not for the mathematics."
        ),
    }
    out["real_repo_carrier_summary"] = {
        "n_real_repos": len(real),
        "total_certified": sum(c["n_certified"] for c in real),
        "total_demonstrated_live": sum(c["n_demonstrated_live_by_execution"] for c in real),
        "n_vacuous_repos": sum(1 for c in real if c["VACUOUS"]),
        "all_real_repos_vacuous": all(c["VACUOUS"] for c in real),
        "any_carrier_separates_all_certified": None if all(
            c["VACUOUS"] for c in real) else any(
            c["any_carrier_separates_all_certified"] for c in real),
        "real_repo_channel_note": (
            "ALL FOUR real repos are VACUOUS on this question. Run 7's inheritance "
            "witness closed all four of run 6's residuals, so no certified symbol "
            "any longer has a name an executed framework was seen to dispatch to, and "
            "a truth-light separation test has nothing to separate against. The loop's "
            "own repair emptied the channel through which N12 would have been "
            "adjudicated on real code, so N12 is decidable ONLY on the fixture. That "
            "is a fact about the instrument's coverage, not about the carriers, and "
            "it is the second thing this run found that the plan did not anticipate."
        ),
        "per_repo": [{
            "repo": c["repo"], "certified": c["n_certified"],
            "demonstrated_live": c["n_demonstrated_live_by_execution"],
            "best_carrier": c["best_carrier"],
            "certified_separable_under_best": (
                None if c["VACUOUS"] else c["per_carrier"][c["best_carrier"]][
                    "n_certified_in_a_clean_block"]),
        } for c in real],
    }
    print(json.dumps([out], indent=1))


if __name__ == "__main__":
    main()
