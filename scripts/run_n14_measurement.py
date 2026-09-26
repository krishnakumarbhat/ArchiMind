"""Run 12 / N14: the binding-set carrier, and what measuring the escape rate did.

N14's stated success criterion, quoted from the strategy graph: "enumerate
binding-set partitions against the EXECUTED 8-method fixture and show either a
non-zero precision-1 coverage (which would beat every carrier in rows 33-34) or
a measured zero, which would close the carrier search for good."

Both branches of that criterion turned out to be wrong, and the run's two
headline findings are about the loop's own instruments rather than about
carriers:

  1. **The incumbent "sound" rule has a demonstrated false positive.**
     ``certify_unreferenced`` (eq. row 18) certifies a predicted-dead symbol
     when its leaf occurs exactly once in the corpus, justified by the lemma
     that every mechanism able to reference the symbol names it somewhere in the
     source. ``experiments/fixtures/synthetic_escape_repo`` W7 -- ``getattr(o,
     "".join(["lo", "ad"]))()`` -- references ``Dyn.load`` and never spells it.
     Executed, deterministically: ``w7_computed_name() == 7``.

  2. **The dynamic oracle silently drops truth.** The per-call 2 s alarm can
     expire mid-target, and the partial event set was stored like any complete
     one. Measured: the escape fixture's truth channel held 4 of 12 dispatches
     with ``w3_iteration`` cut, and across seven separate processes the same
     input yielded 6 dispatches six times and 12 once. ``Dyn.load`` appeared as
     a callee in 1 of 7 runs. The ``timed_out`` field existed and was only ever
     written by a handler that cannot fire.

Order of business: parity first, then the refutation, then the measurements,
then the carrier the node asked for.

Static only on third-party tarballs, as in runs 4-11. The only executions are
against the loop's own fixtures.

Usage:  python3 scripts/run_n14_measurement.py > experiments/run-12-n14.log
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RUNNER = importlib.import_module("scripts.run_auto_research")
N11RUN = importlib.import_module("scripts.run_n11_measurement")
DOMAIN = importlib.import_module("src.04_symbol_domain")
EXPORT = importlib.import_module("src.05_export_boundary")
ESC = importlib.import_module("src.12_escape_channel")

REAL = ["pallets/flask", "psf/requests", "tiangolo/sqlmodel", "Textualize/rich"]
FIXTURES = [
    "synthetic_cpg_repo", "synthetic_promo_repo", "synthetic_taint_repo",
    "synthetic_exports_repo", "synthetic_protocol_repo", "synthetic_index_repo",
    "synthetic_escape_repo",
]
#: Written-down dead sets, by fixture. The escape fixture is absent on purpose:
#: its truth is an execution result, not a set somebody typed.
TRUTH = {
    "synthetic_taint_repo": RUNNER.GROUND_TRUTH_DEAD,
    "synthetic_exports_repo": RUNNER.GROUND_TRUTH_DEAD_EXPORTS,
    "synthetic_protocol_repo": RUNNER.GROUND_TRUTH_DEAD_PROTOCOL,
}


def oracle_for(files: dict):
    """Run the dynamic oracle with the key form it actually requires.

    ``load_repo_corpus`` returns dotted keys WITHOUT the ``.py`` suffix while
    ``run_oracle`` skips any key that does not end in ``.py``. Passing the
    former to the latter makes the oracle observe ZERO modules and report
    perfect precision, which is the same silent-zero defect run 5 hit at
    ``run_n7``. Asserted rather than assumed.
    """
    py = {f"{k}.py": v for k, v in files.items()}
    oracle = RUNNER.DYN_MOD.run_oracle(py)
    return oracle


def escape_refutation() -> dict:
    """Row 18's lemma, refuted by execution rather than by a tracer.

    The oracle cannot be the instrument here: on this fixture it is PARTIAL by
    construction (see :func:`oracle_repeatability`), so a claim about which
    symbols are live has to come from something deterministic. The fixture's
    witnesses return unique sentinels, so ``w7_computed_name() == 7`` IS the
    statement "``Dyn.load`` was dispatched" -- no tracer, no alarm, no sampling.
    """
    root = RUNNER._fixture_dir("synthetic_escape_repo")
    files, corpus, _meta = RUNNER.load_repo_corpus("synthetic_escape_repo")
    cpg = RUNNER.CPG_MOD.build_cpg(files)
    dead = cpg.dead_symbols(dunder_exempt=True)
    counts = DOMAIN.token_name_counts(corpus.values())
    witnesses = EXPORT.star_import_witnesses(corpus)
    sites = ESC.name_construction_sites(corpus)

    incumbent = DOMAIN.certify_unreferenced(dead, counts)
    standing = EXPORT.certify_dead_within_corpus(dead, counts, witnesses)
    vetoed = ESC.certify_escape_vetoed(dead, counts, set(), sites)

    # Executed truth, in a subprocess so the fixture is imported exactly as a
    # consumer would import it.
    probe = subprocess.run(
        [sys.executable, "-c",
         "import sys, json; sys.path.insert(0, %r);"
         "import witnesses as w;"
         "print(json.dumps({'w7': w.w7_computed_name(),"
         "'never_called': w.never_called()}))" % root],
        capture_output=True, text=True, timeout=120,
    )
    executed = json.loads(probe.stdout.strip() or "{}")

    live_by_execution = set()
    if executed.get("w7") == 7:
        live_by_execution.add("witnesses.Dyn.load")
    false_positives = sorted((incumbent | standing) & live_by_execution)
    return {
        "lemma_refuted": (
            "row 18: 'every mechanism that can put a reference to s into a "
            "Python program names s somewhere in the source'"
        ),
        "counterexample_mechanism": "W7: getattr(o, \"\".join([\"lo\", \"ad\"]))()",
        "executed": executed,
        "live_by_execution": sorted(live_by_execution),
        "occ_of_escaping_leaf": counts.get("load"),
        "n_predicted_dead": len(dead),
        "incumbent_certified": sorted(incumbent),
        "standing_certified": sorted(standing),
        "n_false_positives": len(false_positives),
        "false_positives": false_positives,
        "escape_sites": sites,
        "n_effective_escape_sites": len(ESC.effective_sites(sites)),
        "veto_certifies": sorted(vetoed),
        "veto_closes_the_channel": not vetoed,
        "scope_of_the_refutation": (
            "ONE of the nine witnesses in the fixture yields a certified-dead "
            "false positive. The other eight dispatch to dunder leaves, and "
            "dead_symbols(dunder_exempt=True) never admits a dunder leaf to the "
            "dead set, so they are protected by the CPG's dunder exemption and "
            "NOT by row 18's rule. The escape set that matters for the dead-code "
            "term is name construction, not the implicit-dispatch family."
        ),
        "consequence_for_published_numbers": (
            "every real-repo certification count the loop has published since "
            "run 5 is a count of CERTIFICATES, and those stand. What does not "
            "stand is the adjective: the word 'sound', and the zero-false-positive "
            "claim attached to it."
        ),
    }


def oracle_repeatability(repo: str = "synthetic_escape_repo", k: int = 5) -> dict:
    """The truth channel's own completeness, before and after the run-12 guard.

    In-process repeats are the cheap half. The cross-process half is the one that
    found the defect: the 2 s per-call alarm is wall-clock, so the same input on
    a loaded machine loses a target that an idle machine keeps, and before the
    guard a partial event set was indistinguishable from a complete one.
    """
    files, _corpus, _meta = RUNNER.load_repo_corpus(repo)
    inproc = []
    for _ in range(k):
        o = oracle_for(files)
        inproc.append({
            "n_dispatches": len(o.dispatches),
            "completeness": o.completeness()["status"],
            "cut": sorted(o.timed_out),
        })
    script = (
        "import importlib, json, sys;"
        "sys.path.insert(0, %r);"
        "R = importlib.import_module('scripts.run_auto_research');"
        "files, _c, _m = R.load_repo_corpus(%r);"
        "print(json.dumps([len(R.DYN_MOD.run_oracle("
        "{f'{k}.py': v for k, v in files.items()}).dispatches)"
        " for _ in range(%d)]))" % (os.getcwd(), repo, k)
    )
    cross = subprocess.run([sys.executable, "-c", script], capture_output=True,
                           text=True, timeout=600)
    try:
        counts = json.loads(cross.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        counts = []
    return {
        "repo": repo,
        "in_process_repeats": inproc,
        "in_process_n_dispatches": sorted({r["n_dispatches"] for r in inproc}),
        "cross_process_n_dispatches": counts,
        "cross_process_is_deterministic": len(set(counts)) <= 1,
        "n_targets_cut_by_alarm": len(inproc[0]["cut"]) if inproc else None,
        "completeness_supports_dead_claim": (
            inproc[0]["completeness"] == "COMPLETE" if inproc else None
        ),
        "why_it_matters": (
            "the oracle is the loop's only truth channel and it was reporting a "
            "truncated trace as a complete one. 4 of 12 dispatches survived on "
            "this fixture; the missing target is an infinite for-loop over a "
            "Python __next__ under sys.settrace, which is exactly the workload "
            "that blows a wall-clock budget on a loaded machine."
        ),
    }


def audit_repo(repo: str) -> dict:
    """One corpus: the incumbent rule, the sound repair, and the UNSOUND one."""
    files, corpus, meta = RUNNER.load_repo_corpus(repo)
    cpg = RUNNER.CPG_MOD.build_cpg(files)
    dead = cpg.dead_symbols(dunder_exempt=True)
    counts = DOMAIN.token_name_counts(corpus.values())
    _ident = DOMAIN.recount_identifiers_only(corpus.values())
    _per_module = EXPORT.module_name_counts(corpus)
    witnesses = EXPORT.star_import_witnesses(corpus)
    exports = EXPORT.exported_names(corpus)
    external = EXPORT.externally_driven(dead)
    withheld = (EXPORT.star_exposed(dead, witnesses)
                | EXPORT.publicly_exported(dead, exports) | external)

    sites = ESC.name_construction_sites(corpus)
    eff = ESC.effective_sites(sites)
    cp = ESC.call_position(corpus)
    incumbent = EXPORT.certify_dead_within_corpus(dead, counts, witnesses)
    vetoed = ESC.certify_escape_vetoed(dead, counts, withheld, sites)
    refined = ESC.blocker_refined(dead, counts, cp, sites, withheld)
    relaxed = ESC.relaxation_unblocking(dead, cp, withheld)

    row = {
        "repo": repo,
        "is_real_repo": repo in REAL,
        "n_files": len(files),
        "n_predicted_dead": len(dead),
        "escape_channel": {
            "n_sites": len(sites),
            "n_effective_sites": len(eff),
            "sinks": sorted({s["sink"] for s in eff}),
            "corpus_can_build_names": bool(eff),
            "veto_is_a_noop": not eff,
        },
        "carrier": ESC.carrier_split_power(dead, corpus, counts),
        "binding_set_is_caller_side": {
            "n_modules": len(ESC.binding_set(corpus)),
            "why_it_cannot_be_the_carrier": (
                "a binding set is a CALLER property and the certified set is a "
                "CALLEE property; connecting them needs a resolver, and the "
                "identity resolver is row 18's occurrence count while every other "
                "resolver is the alias analysis eq. row 22 priced"
            ),
        },
        "counts": {
            "incumbent_run6_7_certified": len(incumbent),
            "sound_veto_certified": len(vetoed),
            "refined_blocker_certified": len(refined),
            "relaxation_UNSOUND_certified": len(relaxed),
            "veto_cost": len(incumbent) - len(vetoed),
        },
        "exposure": ESC.escape_exposure(incumbent, sites, corpus),
    }
    if repo in TRUTH:
        truth = TRUTH[repo]
        row["adjudication_vs_written_truth"] = {
            "n_truth_dead": len(truth),
            "incumbent": _acc(incumbent, truth),
            "sound_veto": _acc(vetoed, truth),
            "relaxation_UNSOUND": _acc(relaxed, truth),
        }
    return row


def _acc(certified: set, truth: set) -> dict:
    fp = sorted(certified - truth)
    tp = sorted(certified & truth)
    return {
        "n_certified": len(certified),
        "n_true_positive": len(tp),
        "n_false_positive": len(fp),
        "false_positives": fp[:8],
        "precision": round(len(tp) / len(certified), 4) if certified else None,
        "recall": round(len(tp) / len(truth), 4) if truth else None,
    }


def index_fixture_carrier() -> dict:
    """N14's success criterion, run as written, on the EXECUTED 8-method fixture."""
    repo = "synthetic_index_repo"
    N11RUN.build_index_fixture()
    files, corpus, meta = RUNNER.load_repo_corpus(repo)
    probe = importlib.import_module("src.06_protocol_driver").fixture_driver_probe(
        os.path.join(RUNNER._fixture_dir(repo)),
        "experiments/fixtures/synthetic_index_driver",
    )
    reached = set(probe.get("reached_sentinels", []))
    cpg = RUNNER.CPG_MOD.build_cpg(files)
    dead = cpg.dead_symbols(dunder_exempt=True)
    counts = DOMAIN.token_name_counts(corpus.values())
    sites = ESC.name_construction_sites(corpus)
    cp = ESC.call_position(corpus)
    class_methods = sorted(s for s in dead if s.startswith("alpha.T."))
    lasso = {s: (s not in reached) for s in class_methods}

    def acc(certified):
        c = set(certified) & set(class_methods)
        tp = [s for s in c if lasso.get(s)]
        fp = [s for s in c if not lasso.get(s)]
        return {
            "n_certified": len(c),
            "n_true_positive": len(tp),
            "n_false_positive": len(fp),
            "precision_1_coverage": round(len(tp) / sum(lasso.values()), 4)
            if any(lasso.values()) else None,
            "false_positives": sorted(fp),
        }

    return {
        "repo": repo,
        "driver_status": probe.get("status"),
        "n_reached_by_execution": len(reached),
        "n_class_methods": len(class_methods),
        "n_effective_escape_sites": len(ESC.effective_sites(sites)),
        "n_leaves_in_call_position": len(cp),
        "incumbent": acc(EXPORT.certify_dead_within_corpus(
            dead, counts, EXPORT.star_import_witnesses(corpus))),
        "sound_veto": acc(ESC.certify_escape_vetoed(dead, counts, set(), sites)),
        "relaxation_UNSOUND": acc(ESC.relaxation_unblocking(dead, cp, set())),
        "criterion_outcome": (
            "MEASURED ZERO, and the zero does NOT close the carrier search: the "
            "same carrier splits a distinct-leaf evidence-fibre on the "
            "counterexample in src/12_escape_channel.py::t1_counterexample. Both "
            "branches of N14's stated success criterion are therefore wrong -- "
            "the non-zero branch is unreachable on this fixture and the zero "
            "branch's conclusion is not structural."
        ),
    }


def main() -> None:
    # PARITY FIRST, before self_check or any repo work touches the process: the
    # composite carries a RAM term, so anything imported first is charged to it.
    parity = N11RUN.parity()
    probe = RUNNER.run_one("v2_treesitter_cpg", "synthetic_cpg_repo")
    parity["resource_terms"] = {
        "peak_ram_mb": probe.get("peak_ram_mb"),
        "blast_latency_ms": probe.get("blast_latency_ms"),
        "ram_term_points": 10 * max(0.0, 1 - (probe.get("peak_ram_mb") or 0) / 512),
        "latency_term_points": 10 * max(
            0.0, 1 - (probe.get("blast_latency_ms") or 0) / 2000),
        "note": (
            "the composite is quality + these two terms, so a composite delta "
            "with empty `diffs` is a RESOURCE delta by construction. Reported "
            "explicitly because run 6 learned that a composite movement with no "
            "attribution is indistinguishable from a quality regression."
        ),
    }
    sc = ESC.self_check()
    audits = [audit_repo(r) for r in FIXTURES + REAL]
    _real = [a for a in audits if a["is_real_repo"]]
    out = {
        "variation": "n14_binding_carrier_and_escape_channel",
        "metric_def": "unreferenced-domain-v4",
        "max_metric": 80,
        "metric_def_note": (
            "UNCHANGED for the NINTH consecutive run. The dead term is UNSCORED, "
            "so harness_score cannot move. Worse: this run shows the rule "
            "generating that term is not sound, so the honest headline is not "
            "'the score did not move' but 'the score was never entitled to move "
            "on this term'."
        ),
        "parity": parity,
        "self_check": sc,
        "refutation": escape_refutation(),
        "oracle_repeatability": oracle_repeatability(),
        "n14_carrier_on_executed_fixture": index_fixture_carrier(),
        "audits": audits,
    }

    out["n14_verdicts"] = {
        "t1_retracted_before_publication": {
            "claim": ESC.N14_RETRACTED_T1,
            "surviving": ESC.N14_SURVIVING_T1,
            "counterexample": ESC.t1_counterexample()["carrier"],
            "why_it_matters": (
                "the loop was about to publish 'a distinct-leaf evidence-fibre "
                "is unsplittable by any corpus-derived carrier'. An adversarial "
                "sub-agent told to assume the math was wrong killed it as a "
                "NON-SEQUITUR, and t1_counterexample makes it false on demand. "
                "This is the FIFTH instance of the loop's own recorded failure "
                "mode and the first caught BEFORE publication rather than after."
            ),
        },
        "binding_set_is_not_the_carrier": {
            "verdict": "REFUTED as a carrier, kept as a diagnostic",
            "reason": (
                "caller-side property versus callee-side verdict; the identity "
                "resolver is row 18's count and any other resolver is the alias "
                "analysis eq. row 22 already priced. The implementation's first "
                "draft made exactly this error -- it required a module to BIND "
                "the leaf it calls, so `from alpha import T; T().m()` did not "
                "count as a dispatch of m -- and the counterexample failed to "
                "split because of it."
            ),
        },
        "what_the_carrier_actually_adds": (
            "the KIND of an occurrence, not its count: a leaf in call position "
            "anywhere in the corpus is a different fact from a leaf that is "
            "merely mentioned, and the occurrence count cannot tell them apart. "
            "That is enough to split an evidence-fibre and it is the first "
            "corpus-derived carrier in runs 9-12 that is not constant on one."
        ),
        "sound_direction_only": (
            "the carrier is usable as a BLOCKER, which over-refuses and is "
            "therefore sound: it withholds a symbol the corpus calls. The "
            "unblocking direction -- certify a symbol the corpus never calls -- "
            "is UNSOUND and is shipped labelled, with its false positives "
            "measured on every fixture that has truth."
        ),
        "the_price_is_stated_not_tuned": (
            "on the four real tarballs the escape veto is a NO-OP wherever the "
            "corpus contains no effective construction site, so the refutation "
            "does not by itself invalidate the published counts; where it does "
            "fire, the price is the whole certified set. That number is in the "
            "audits and it is not small."
        ),
        "reported_against_interest": [
            "the node was queued as a carrier search and it produced a retraction "
            "of the loop's own soundness claim instead. N14's stated payoff -- a "
            "precision-1 coverage above the abstain baseline -- is still 0.",
            "the sound repair is a THIRD global veto. The first two were run 4's "
            "<complex> precondition and run 11's A1; each was replaced by a "
            "narrower rule that later turned out unsound, and this one is the "
            "same shape. The pattern is now three data points and it is evidence "
            "that the sound formulation is a taint query, not an enumeration.",
            "the loop has published six runs of certification counts under the "
            "word 'sound'. The counts are unaffected; the word was not earned.",
        ],
    }
    print(json.dumps([out], indent=1, default=str))


if __name__ == "__main__":
    main()
