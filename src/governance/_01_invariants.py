"""Structural Clean Architecture rule verifier (3 invariants)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

import networkx as nx

from src.config._01_constants import (
    INVARIANT_ACYCLIC,
    INVARIANT_DOMAIN_PURITY,
    INVARIANT_PRESENTATION_ISOLATION,
)
from src.cpg._01_cpg_builder import EDGE_CALLS, EDGE_IMPORTS


@dataclass
class InvariantVerdict:
    """Pass/fail verdict for one architectural invariant."""

    id: str
    passed: bool
    details: List[str] = field(default_factory=list)


class ArchitectureInvariantChecker:
    """Evaluates layering, acyclicity, and domain-purity rules on a CPG."""

    def __init__(self, graph: nx.DiGraph[Any]) -> None:
        """Bind the checker to a built code property graph."""
        self._graph = graph

    @staticmethod
    def _layer_of(path: object) -> str:
        """Classify a file path into presentation/data/domain/other."""
        p = str(path or "").lower()
        if any(k in p for k in ("route", "view", "present", "api", "handler", "controller")):
            return "presentation"
        if any(k in p for k in ("repo", "dao", "store", "db", "model", "entity", "schema")):
            return "data"
        if any(k in p for k in ("service", "usecase", "use_case", "domain", "core")):
            return "domain"
        return "other"

    def _name(self, node: str) -> str:
        """Resolve a node id to its display name."""
        return str(self._graph.nodes[node].get("name") or node)

    def _structural_edges(self) -> List[Tuple[str, str, Any]]:
        """List import/call edges as (src, dst, kind) triples."""
        return [(u, v, d.get("kind")) for u, v, d in self._graph.edges(data=True)]

    def check_presentation_isolation(self) -> InvariantVerdict:
        """Flag presentation files importing data-layer files directly."""
        direct = [
            f"{self._name(u)} -> {self._name(v)}"
            for u, v, k in self._structural_edges()
            if k in (EDGE_IMPORTS, EDGE_CALLS)
            and self._layer_of(self._graph.nodes[u].get("path")) == "presentation"
            and self._layer_of(self._graph.nodes[v].get("path")) == "data"
        ]
        return InvariantVerdict(id=INVARIANT_PRESENTATION_ISOLATION, passed=not direct, details=direct[:20])

    def check_acyclic(self) -> InvariantVerdict:
        """Flag any dependency cycle in the graph."""
        try:
            cycle = list(nx.find_cycle(self._graph, orientation="original"))
            cyc = [f"{self._name(u)} -> {self._name(v)}" for u, v, _ in cycle]
        except nx.NetworkXNoCycle:
            cyc = []
        return InvariantVerdict(id=INVARIANT_ACYCLIC, passed=not cyc, details=cyc[:20])

    def check_domain_purity(self) -> InvariantVerdict:
        """Flag domain files depending on infrastructure modules."""
        bad = [
            f"{self._name(u)} -> {self._name(v)}"
            for u, v, k in self._structural_edges()
            if k in (EDGE_IMPORTS, EDGE_CALLS)
            and self._layer_of(self._graph.nodes[u].get("path")) == "domain"
            and any(
                k in str(self._graph.nodes[v].get("path") or "").lower()
                for k in ("infra", "external", "third")
            )
        ]
        return InvariantVerdict(id=INVARIANT_DOMAIN_PURITY, passed=not bad, details=bad[:20])

    def check_all(self) -> List[Dict[str, Any]]:
        """Evaluate every invariant and return JSON-safe verdicts."""
        return [
            {"id": v.id, "passed": v.passed, "details": v.details}
            for v in (self.check_presentation_isolation(), self.check_acyclic(), self.check_domain_purity())
        ]
