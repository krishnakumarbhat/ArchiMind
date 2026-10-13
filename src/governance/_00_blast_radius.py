"""Downstream BFS reachability (blast radius) over a compact CPG artifact."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.cpg._01_cpg_builder import CodePropertyGraphBuilder


@dataclass
class BlastRadiusResult:
    """Transitive impact of changing one symbol."""

    symbol: str
    impacted: List[str] = field(default_factory=list)
    edges: int = 0
    ms: float = 0.0


class ReverseBlastRadiusEngine:
    """Computes what breaks when a symbol changes (callers, not callees)."""

    def __init__(self, artifact: Dict[str, Any]) -> None:
        """Rebuild the graph once from a compact artifact."""
        started = time.time()
        self._graph = CodePropertyGraphBuilder.from_compact(artifact)
        self._load_ms = round((time.time() - started) * 1000, 2)

    def compute_impact(self, symbol: str) -> BlastRadiusResult:
        """Return impacted downstream symbols plus timing for a changed symbol."""
        started = time.time()
        names: List[str] = []
        for node_id in CodePropertyGraphBuilder.blast_radius(self._graph, symbol):
            name = self._graph.nodes[node_id].get("name") or node_id
            if name not in names:
                names.append(str(name))
        return BlastRadiusResult(
            symbol=symbol,
            impacted=names,
            edges=len(names),
            ms=round((time.time() - started) * 1000, 2),
        )
