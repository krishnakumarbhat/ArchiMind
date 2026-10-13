"""Deterministic CPG tools for the agentic assistant (no LLM calls)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Set

import networkx as nx

from src.cpg._01_cpg_builder import CodePropertyGraphBuilder
from src.governance._01_invariants import ArchitectureInvariantChecker

logger = logging.getLogger(__name__)


class CPGInspectionToolSuite:
    """Deterministic code-graph tools bound to one built graph."""

    def __init__(self, graph: nx.DiGraph[Any]) -> None:
        """Bind the suite to a code property graph."""
        self._graph = graph

    def trace_symbol_impact(self, symbol: str) -> Dict[str, Any]:
        """Return the downstream blast radius of a symbol."""
        hit = CodePropertyGraphBuilder.blast_radius(self._graph, symbol)
        names: List[str] = []
        for node_id in hit:
            name = self._graph.nodes[node_id].get("name") or node_id
            if name not in names:
                names.append(str(name))
        return {"tool": "trace_symbol_impact", "symbol": symbol, "impacted": names, "edges": len(names)}

    def verify_rules(self) -> Dict[str, Any]:
        """Run the Clean Architecture invariant check."""
        results = ArchitectureInvariantChecker(self._graph).check_all()
        return {
            "tool": "verify_architecture_rules",
            "passed": all(r["passed"] for r in results),
            "rules": results,
        }

    def get_symbol_ast(self, symbol: str) -> Dict[str, Any]:
        """Return definition records and callers for a symbol."""
        matches = [
            {"id": str(n), "kind": d.get("kind"), "name": d.get("name"), "path": d.get("path")}
            for n, d in self._graph.nodes(data=True)
            if d.get("name") == symbol or str(n).endswith("::" + symbol)
        ]
        callers: Set[str] = set()
        for m in matches:
            callers.update(str(p) for p in self._graph.predecessors(m["id"]))
        return {
            "tool": "get_symbol_ast",
            "symbol": symbol,
            "matches": matches[:10],
            "called_by": sorted(callers)[:20],
        }
