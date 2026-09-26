"""Structural Clean Architecture rule verifier (3 invariants)."""
from __future__ import annotations

from typing import Any, Dict, List

import networkx as nx

from src.config._01_constants import (
    INVARIANT_ACYCLIC,
    INVARIANT_DOMAIN_PURITY,
    INVARIANT_PRESENTATION_ISOLATION,
)
from src.cpg._01_cpg_builder import EDGE_CALLS, EDGE_IMPORTS


def _names(g: nx.DiGraph[Any], node: str) -> str:
    return str(g.nodes[node].get("name") or node)


def check_invariants(g: nx.DiGraph[Any]) -> List[Dict[str, Any]]:
    """Evaluate invariants; return [{id, passed, details}]."""
    results: List[Dict[str, Any]] = []
    edges = [(u, v, d.get("kind")) for u, v, d in g.edges(data=True)]

    def layer_of(path: object) -> str:
        p = str(path or "").lower()
        if any(k in p for k in ("route", "view", "present", "api", "handler", "controller")):
            return "presentation"
        if any(k in p for k in ("repo", "dao", "store", "db", "model", "entity", "schema")):
            return "data"
        if any(k in p for k in ("service", "usecase", "use_case", "domain", "core")):
            return "domain"
        return "other"

    direct = [
        f"{_names(g, u)} -> {_names(g, v)}"
        for u, v, k in edges
        if k in (EDGE_IMPORTS, EDGE_CALLS)
        and layer_of(g.nodes[u].get("path")) == "presentation"
        and layer_of(g.nodes[v].get("path")) == "data"
    ]
    results.append({"id": INVARIANT_PRESENTATION_ISOLATION, "passed": not direct, "details": direct[:20]})

    try:
        cycle = list(nx.find_cycle(g, orientation="original"))
        cyc = [f"{_names(g, u)} -> {_names(g, v)}" for u, v, _ in cycle]
    except nx.NetworkXNoCycle:
        cyc = []
    results.append({"id": INVARIANT_ACYCLIC, "passed": not cyc, "details": cyc[:20]})

    domain_bad = [
        f"{_names(g, u)} -> {_names(g, v)}"
        for u, v, k in edges
        if k in (EDGE_IMPORTS, EDGE_CALLS)
        and layer_of(g.nodes[u].get("path")) == "domain"
        and any(k in str(g.nodes[v].get("path") or "").lower() for k in ("infra", "external", "third"))
    ]
    results.append({"id": INVARIANT_DOMAIN_PURITY, "passed": not domain_bad, "details": domain_bad[:20]})
    return results
