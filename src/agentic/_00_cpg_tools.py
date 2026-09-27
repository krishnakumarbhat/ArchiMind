"""Deterministic CPG tools for the agentic assistant (no LLM calls)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Set

import networkx as nx

logger = logging.getLogger(__name__)


def trace_symbol_impact(symbol: str, g: nx.DiGraph[Any]) -> Dict[str, Any]:
    """Downstream blast radius of a symbol (tool: trace_symbol_impact)."""
    from src.cpg._01_cpg_builder import blast_radius

    hit = blast_radius(g, symbol)
    names: List[str] = []
    for node_id in hit:
        name = g.nodes[node_id].get("name") or node_id
        if name not in names:
            names.append(str(name))
    return {"tool": "trace_symbol_impact", "symbol": symbol, "impacted": names, "edges": len(names)}


def verify_architecture_rules(g: nx.DiGraph[Any]) -> Dict[str, Any]:
    """Clean-architecture invariant check (tool: verify_architecture_rules)."""
    from src.governance._01_invariants import check_invariants

    results = check_invariants(g)
    return {
        "tool": "verify_architecture_rules",
        "passed": all(r["passed"] for r in results),
        "rules": results,
    }


def get_symbol_ast(symbol: str, g: nx.DiGraph[Any]) -> Dict[str, Any]:
    """Exact class/function signature record (tool: get_symbol_ast)."""
    matches = [
        {"id": str(n), "kind": d.get("kind"), "name": d.get("name"), "path": d.get("path")}
        for n, d in g.nodes(data=True)
        if d.get("name") == symbol or str(n).endswith("::" + symbol)
    ]
    callers: Set[str] = set()
    for m in matches:
        callers.update(str(p) for p in g.predecessors(m["id"]))
    return {"tool": "get_symbol_ast", "symbol": symbol, "matches": matches[:10], "called_by": sorted(callers)[:20]}
