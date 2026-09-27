"""'Challenge Me' SWE harness: synthesize onboarding tasks from CPG seams."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import networkx as nx

logger = logging.getLogger(__name__)


def _leaf(name: object) -> str:
    return str(name).split(".")[-1]


def find_seams(g: nx.DiGraph[Any], limit: int = 8) -> List[Dict[str, Any]]:
    """Functions with zero in-corpus callers (untested seams), ranked by fan-out."""
    from src.cpg._01_cpg_builder import EDGE_CALLS, NODE_FUNC

    seams: List[Dict[str, Any]] = []
    for n, d in g.nodes(data=True):
        if d.get("kind") != NODE_FUNC:
            continue
        callers = [p for p in g.predecessors(n) if g.edges[p, n].get("kind") == EDGE_CALLS]
        if callers:
            continue
        fanout = sum(1 for s in g.successors(n) if g.edges[n, s].get("kind") == EDGE_CALLS)
        seams.append(
            {"id": str(n), "name": str(d.get("name")), "path": str(d.get("path")), "fanout": fanout}
        )
    seams.sort(key=lambda s: -s["fanout"])
    return seams[:limit]


def _starter_for(symbol: str, path: str) -> str:
    leaf = _leaf(symbol)
    return (
        f"# Challenge: give `{leaf}` (in {path}) its first test.\n"
        f"# 1. Read the function and list its inputs/edge cases.\n"
        f"# 2. Implement `test_{re.sub(r'[^0-9a-zA-Z_]', '_', leaf)}` below.\n"
        f"# 3. Run: python3 -m pytest <this_file>\n\n"
        f"def test_{re.sub(r'[^0-9a-zA-Z_]', '_', leaf)}():\n"
        f"    raise NotImplementedError('write your first assertion for {leaf}')\n"
    )


def generate_challenge(g: nx.DiGraph[Any], index: int = 0) -> Optional[Dict[str, Any]]:
    """Build one challenge schema from the weakest untested seam."""
    seams = find_seams(g)
    if not seams:
        return None
    seam = seams[index % len(seams)]
    leaf = _leaf(seam["name"])
    return {
        "title": f"Test the untested: {leaf}",
        "description": (
            f"`{seam['name']}` in `{seam['path']}` has zero in-corpus callers — no test "
            f"exercises it, yet it reaches {seam['fanout']} downstream symbol(s). "
            "Write the characterization test that locks its current behavior."
        ),
        "target_file": seam["path"],
        "symbol": seam["name"],
        "starter_code": _starter_for(seam["name"], seam["path"]),
        "failing_test": _starter_for(seam["name"], seam["path"]),
        "hints": [
            "Start with the happy path, then null/empty inputs.",
            "If it touches I/O, test the pure logic around it first.",
        ],
    }
