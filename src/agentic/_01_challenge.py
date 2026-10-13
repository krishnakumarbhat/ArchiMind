"""'Challenge Me' SWE harness: synthesize onboarding tasks from CPG seams."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import networkx as nx

from src.cpg._01_cpg_builder import EDGE_CALLS, NODE_FUNC

logger = logging.getLogger(__name__)


class SWEChallengeHarness:
    """Generates failing-test onboarding tasks from untested code seams."""

    def __init__(self, graph: nx.DiGraph[Any], limit: int = 8) -> None:
        """Bind the harness to a graph with a cap on ranked seams."""
        self._graph = graph
        self._limit = limit

    @staticmethod
    def _leaf(name: object) -> str:
        """Extract the trailing symbol from a qualified name."""
        return str(name).split(".")[-1]

    def find_seams(self) -> List[Dict[str, Any]]:
        """List functions with zero in-corpus callers, ranked by fan-out."""
        seams: List[Dict[str, Any]] = []
        for n, d in self._graph.nodes(data=True):
            if d.get("kind") != NODE_FUNC:
                continue
            callers = [
                p for p in self._graph.predecessors(n) if self._graph.edges[p, n].get("kind") == EDGE_CALLS
            ]
            if callers:
                continue
            fanout = sum(
                1 for s in self._graph.successors(n) if self._graph.edges[n, s].get("kind") == EDGE_CALLS
            )
            seams.append(
                {"id": str(n), "name": str(d.get("name")), "path": str(d.get("path")), "fanout": fanout}
            )
        seams.sort(key=lambda s: -s["fanout"])
        return seams[: self._limit]

    def _starter_for(self, symbol: str, path: str) -> str:
        """Scaffold a failing pytest file for one symbol."""
        leaf = self._leaf(symbol)
        safe = re.sub(r"[^0-9a-zA-Z_]", "_", leaf)
        return (
            f"# Challenge: give `{leaf}` (in {path}) its first test.\n"
            f"# 1. Read the function and list its inputs/edge cases.\n"
            f"# 2. Implement `test_{safe}` below.\n"
            f"# 3. Run: python3 -m pytest <this_file>\n\n"
            f"def test_{safe}():\n"
            f"    raise NotImplementedError('write your first assertion for {leaf}')\n"
        )

    def generate(self, index: int = 0) -> Optional[Dict[str, Any]]:
        """Build one challenge schema from the weakest untested seam."""
        seams = self.find_seams()
        if not seams:
            return None
        seam = seams[index % len(seams)]
        leaf = self._leaf(seam["name"])
        starter = self._starter_for(seam["name"], seam["path"])
        return {
            "title": f"Test the untested: {leaf}",
            "description": (
                f"`{seam['name']}` in `{seam['path']}` has zero in-corpus callers — no test "
                f"exercises it, yet it reaches {seam['fanout']} downstream symbol(s). "
                "Write the characterization test that locks its current behavior."
            ),
            "target_file": seam["path"],
            "symbol": seam["name"],
            "starter_code": starter,
            "failing_test": starter,
            "hints": [
                "Start with the happy path, then null/empty inputs.",
                "If it touches I/O, test the pure logic around it first.",
            ],
        }
