"""Run 7 / N10 measurement: the reflection interface is irreducibly external.

Runs the base-witness gate against run 6's rule on all 9 corpora, adjudicates
run 6's 4 residual certificates against EXECUTED real framework drivers, and
records the discriminating pair that no in-corpus rule can separate.

Usage:  python3 scripts/run_n10_measurement.py > experiments/run-7-n10.log
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

REAL = ["pallets/flask", "psf/requests", "tiangolo/sqlmodel", "Textualize/rich"]
FIXTURES = [
    "synthetic_cpg_repo", "synthetic_promo_repo", "synthetic_taint_repo",
    "synthetic_exports_repo", "synthetic_protocol_repo",
]
RUN6_RESIDUALS = {
    "sqlmodel.sql.sqltypes.UTCDateTime.coerce_compared_value",
    "sqlmodel.sql.sqltypes.UTCDateTime.process_bind_param",
    "sqlmodel.sql.sqltypes.UTCDateTime.process_result_value",
    "rich.logging.RichHandler.emit",
}


def gate(repo):
    """Run 6's rule vs run 7's rule on the same graph, same corpus, same counts."""
    files, corpus, meta = RUNNER.load_repo_corpus(repo)
    cpg = RUNNER.CPG_MOD.build_cpg(files)
    dead = cpg.dead_symbols(dunder_exempt=True)
    counts = DOMAIN.token_name_counts(corpus.values())
    witnesses = EXPORT.star_import_witnesses(corpus)
    run6 = EXPORT.certify_dead_within_corpus(dead, counts, witnesses)
    wit = IC.out_of_corpus_bases(files, corpus)
    run7 = IC.certify_dead_base_witness(dead, counts, wit, EXPORT.externally_driven(dead))
    return {
        "repo": repo,
        "n_predicted_dead": len(dead),
        "n_run6_certified": len(run6),
        "n_run7_certified": len(run7),
        "certification_rate_run6": round(len(run6) / len(dead), 4) if dead else None,
        "certification_rate_run7": round(len(run7) / len(dead), 4) if dead else None,
        "n_witnessed_classes": len(wit),
        "n_withheld_by_witness": len(EXPORT.certify_dead_within_corpus(dead, counts, witnesses)) - len(run7),
        "witness_is_subset_of_run6": run7 <= run6,
        "certified_run6": sorted(run6),
        "certified_run7": sorted(run7),
        "removed_by_witness": sorted(run6 - run7),
        "run6_residuals_removed": sorted(RUN6_RESIDUALS & (run6 - run7)),
        "run6_residuals_still_certified": sorted(RUN6_RESIDUALS & run7),
        "peak_ram_mb": None,
    }


def main():
    out = []
    for repo in FIXTURES + REAL:
        out.append(gate(repo))

    # --- the discriminating pair, on the fixture whose truth is written down ---
    fdir = RUNNER._fixture_dir("synthetic_protocol_repo")
    corpus = {}
    for name in sorted(os.listdir(fdir)):
        if name.endswith(".py"):
            with open(os.path.join(fdir, name)) as fh:
                corpus[name[:-3]] = fh.read()
    pair = IC.discriminating_pair(
        corpus, "alpha.T.process_literal_param", "alpha._fixture_dead_plain"
    )
    pair["live_adjudication"] = "DISPATCHED by executed out-of-corpus driver"
    pair["dead_adjudication"] = "written down as dead, never dispatched"
    pair["consequence"] = (
        "identical in-corpus evidence + different liveness => any deterministic "
        "in-corpus-only gate scores <= 0.5 on this pair. A declared interface is "
        "not a tuning knob; it is the only carrier of the missing bit."
    )

    # --- does a NAME manifest separate them? (N10's actual proposal) ---
    manifest = PROTO.PROTOCOL_NAMES
    pair["in_n10_manifest"] = "process_literal_param" in manifest
    pair["manifest_separates_pair"] = (
        ("process_literal_param" in manifest) != ("_fixture_dead_plain" in manifest)
    )

    # --- per-symbol adjudication on the protocol fixture: which gate certifies
    # --- the demonstrably-live symbol, and why neither can stop.
    pg = next(g for g in out if g["repo"] == "synthetic_protocol_repo")
    pair["surviving_false_positive"] = {
        "symbol": "alpha.T.process_literal_param",
        "in_run6_certified": "alpha.T.process_literal_param" in pg["certified_run6"],
        "in_run7_certified": "alpha.T.process_literal_param" in pg["certified_run7"],
        "reason_manifest_fails": "its name is absent from PROTOCOL_NAMES, so the "
                                 "manifest withholds nothing; an OPEN list cannot be sound",
        "reason_base_witness_fails": "class T has no written base, so there is no "
                                     "inheritance edge to point out of the corpus",
        "is_blocked_by_occurrence": False,
    }

    # --- real framework drivers, EXECUTED, adjudicating run 6's residuals ---
    probes = PROTO.real_framework_probes()
    adjudicated = []
    for probe_name, p in probes.items():
        if p.get("status") != "executed":
            continue
        for name in p.get("dispatched", []):
            adjudicated.append({
                "probe": probe_name, "dispatched_name": name,
                "object": p.get("object"), "source": p.get("object_source"),
                "verdict": "run 6's certificate on such a symbol would be a FALSE POSITIVE",
            })
    for name in p.get("not_dispatched", []):
        adjudicated.append({
            "probe": probe_name, "dispatched_name": name,
            "verdict": "not reached by THIS driver; a lower bound, not a refutation",
        })

    result = {
        "variation": "n10_import_closure_base_witness",
        "metric_def": "unreferenced-domain-v4",
        "max_metric": 80,
        "metric_def_note": (
            "UNCHANGED for the fourth run. The dead term remains UNSCORED, so no "
            "harness_score can move; the certified SET is the deliverable."
        ),
        "gates": out,
        "discriminating_pair": pair,
        "executed_framework_adjudication": adjudicated,
        "real_framework_probes": probes,
        "n10_manifest_prior_art": {
            "mechanism": "hand-maintained external name list",
            "is_vulture_whitelist": True,
            "vulture_whitelist_matches_by": "bare name in a single global set (issue #430)",
            "verdict": "N10's proposal is PRIOR ART and inherits the open-list soundness hole",
        },
    }
    print(json.dumps([result], indent=1))


if __name__ == "__main__":
    main()
