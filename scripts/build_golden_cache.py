"""Build bundled golden fixtures: subtree fetch -> CPG -> deterministic diagrams + handbook.

Writes src/storage/golden_fixtures/<id>.json (committed, so demos work on any deploy).
Run: python3 scripts/build_golden_cache.py [id ...]
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config._01_constants import GOLDEN_REPOS  # noqa: E402
from src.cpg._01_cpg_builder import NODE_CLASS, NODE_FILE, NODE_FUNC, build_graph, to_compact  # noqa: E402
from src.governance._01_invariants import check_invariants  # noqa: E402
from src.ingestion._02_subtree_client import fetch_subtree  # noqa: E402
from src.orchestration._01_eval_optimizer import validate_mermaid  # noqa: E402
from src.orchestration._03_cpg_diagrams import flow, handbook, hld, lld  # noqa: E402
from src.storage._01_golden_repos import FIXTURE_DIR  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("golden")


def build_one(repo_id: str, title: str, subtitle: str, repo: str, dirs: tuple) -> dict:
    """Fetch a bounded subtree and produce the complete workspace fixture."""
    files = fetch_subtree(repo, dirs)
    g = build_graph(files)
    invariants = check_invariants(g)
    diagrams = {"hld_mermaid": hld(g), "lld_mermaid": lld(g), "flow_mermaid": flow(g)}
    for k, code in diagrams.items():
        err = validate_mermaid(code)
        if err:
            raise RuntimeError(f"{repo_id} {k} invalid: {err}")
    stats = {
        "files": sum(1 for _, d in g.nodes(data=True) if d.get("kind") == NODE_FILE),
        "classes": sum(1 for _, d in g.nodes(data=True) if d.get("kind") == NODE_CLASS),
        "functions": sum(1 for _, d in g.nodes(data=True) if d.get("kind") == NODE_FUNC),
        "edges": g.number_of_edges(),
    }
    return {
        "id": repo_id,
        "name": title,
        "title": title,
        "subtitle": subtitle,
        "repo_url": f"https://github.com/{repo}",
        "scope": list(dirs),
        "stats": stats,
        "chat_summary": f"{title}: {stats['files']} files, {stats['classes']} classes, "
        f"{stats['functions']} functions, {stats['edges']} edges (scope: {', '.join(dirs)}).",
        "chat_response": handbook(g, title, f"{title} — {subtitle}", invariants),
        "invariants": invariants,
        "repair_log": {"hld": 1, "lld": 1, "flow": 1},
        "engine": "ArchiMind v2 CPG Harness",
        **diagrams,
        "cpg_artifact": to_compact(g),
    }


def main() -> None:
    """Build all (or selected) golden fixtures."""
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    wanted = set(sys.argv[1:])
    for spec in GOLDEN_REPOS:
        if wanted and spec[0] not in wanted:
            continue
        try:
            doc = build_one(*spec)
        except Exception as exc:
            logger.error("Golden build failed for %s: %s", spec[0], exc)
            continue
        path = os.path.join(FIXTURE_DIR, f"{spec[0]}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, separators=(",", ":"))
        logger.info("Fixture %s: %s (%d KB)", spec[0], doc["stats"], os.path.getsize(path) // 1024)


if __name__ == "__main__":
    main()
