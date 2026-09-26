"""Run 13 worker: one oracle in a FRESH PROCESS, printed as one JSON line.

Cross-process repeatability is the half of the determinism question that
in-process repeats cannot answer, because they share an interpreter, an import
cache and a warm branch predictor. A wall-clock bound produces a value that is
often stable in-process and unstable across processes, and that asymmetry is the
signature of a machine-load artefact rather than of program state.

Read ``N15_REPO`` and ``N15_KWARGS`` from the environment; print the dispatch
count and the completeness census. Never raises: a worker that dies is itself a
data point, so the caller must be able to see it as ``n_dispatches: null``.

Usage:  N15_REPO=... N15_KWARGS='{}' python3 scripts/run_n15_worker.py
"""

from __future__ import annotations

import importlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RUNNER = importlib.import_module("scripts.run_auto_research")
DYN = RUNNER.DYN_MOD


def main() -> None:
    repo = os.environ["N15_REPO"]
    kwargs = json.loads(os.environ.get("N15_KWARGS", "{}"))
    files, _corpus, _meta = RUNNER.load_repo_corpus(repo)
    py = {f"{k}.py": v for k, v in files.items()}
    try:
        oracle = DYN.run_oracle(py, **kwargs)
        comp = oracle.completeness()
        row = {
            "repo": repo,
            "n_dispatches": len(oracle.dispatches),
            "n_dispatches_digest": sorted(
                f"{a}->{b}" for a, b in oracle.dispatches
            ),
            "n_trace_events": oracle.n_trace_events,
            "status": comp["status"],
            "truth_coverage": comp["truth_coverage"],
            "n_targets": comp["n_targets"],
            "n_targets_cut_by_alarm": comp["n_targets_cut_by_alarm"],
            "n_targets_cut_by_events": comp["n_targets_cut_by_events"],
            "n_targets_errored": comp["n_targets_errored"],
            "bound_kind": comp["bound_kind"],
        }
    except BaseException as exc:  # noqa: BLE001 - a dead worker is a data point
        row = {"repo": repo, "n_dispatches": None, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(row, sort_keys=True))


if __name__ == "__main__":
    main()
