"""10-repo smoke harness: sequential analyses (single-job reality), local backend (no quota burn).

Usage: GEMINI_API_KEY= python3 scripts/smoke_10.py [--out experiments/smoke_10.log]
"""
import json
import logging
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

logging.basicConfig(level=logging.WARNING)

REPOS = [
    "https://github.com/krishnakumarbhat/fdv",
    "https://github.com/LeevAI-Devs/webpage",
    "https://github.com/pallets/flask",
    "https://github.com/psf/requests",
    "https://github.com/tiangolo/sqlmodel",
    "https://github.com/pallets/click",
    "https://github.com/Textualize/rich",
    "https://github.com/pallets/jinja",
    "https://github.com/tartley/colorama",
    "https://github.com/psf/black",
]


def main() -> int:
    """Run all repos sequentially, recording per-repo verdicts."""
    from src.orchestration._01_eval_optimizer import MermaidEvaluatorOptimizer
    from src.orchestration._04_worker import AnalysisWorker

    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "experiments/smoke_10.log"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    results = []
    failures = 0
    t_all = time.time()
    for i, url in enumerate(REPOS, 1):
        row = {"n": i, "repo": url}
        t0 = time.time()
        try:
            w = AnalysisWorker()
            files = w._collect_with_tarball_first(url, f"/tmp/smoke_{i}")
            row["files"] = len(files)
            from src.config._01_constants import CPG_EXTENSIONS
            from src.cpg._01_cpg_builder import CodePropertyGraphBuilder

            src_files = {k: v for k, v in files.items() if k.endswith(CPG_EXTENSIONS)}
            builder = CodePropertyGraphBuilder()
            g = builder.build(dict(list(src_files.items())[:300]))
            row["nodes"] = g.number_of_nodes()
            row["edges"] = g.number_of_edges()
            from src.orchestration._03_cpg_diagrams import CPGDiagramCompiler

            comp = CPGDiagramCompiler(g)
            diags = {"hld": comp.hld(), "lld": comp.lld(), "flow": comp.flow()}
            bad = {
                k: MermaidEvaluatorOptimizer.validate(v)
                for k, v in diags.items()
                if MermaidEvaluatorOptimizer.validate(v)
            }
            row["diagrams_invalid"] = bad
            row["status"] = "PASS" if not bad and files else ("EMPTY" if not files else "FAIL")
        except Exception as exc:
            row["status"] = "ERROR"
            row["error"] = str(exc)[:200]
            traceback.print_exc()
            failures += 1
        row["secs"] = round(time.time() - t0, 1)
        results.append(row)
        print(
            f"[{i}/10] {url.split('/')[-1]:12s} {row['status']:6s} files={row.get('files')} "
            f"nodes={row.get('nodes')} edges={row.get('edges')} {row['secs']}s",
            flush=True,
        )
    summary = {
        "repos": len(REPOS),
        "failures": failures,
        "total_secs": round(time.time() - t_all, 1),
        "rows": results,
    }
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print("SMOKE:", json.dumps({k: v for k, v in summary.items() if k != "rows"}))
    return 1 if failures or any(r["status"] not in ("PASS", "EMPTY") for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
