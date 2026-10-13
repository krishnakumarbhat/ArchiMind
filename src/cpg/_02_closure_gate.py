"""Base-class inheritance closure gate (no hand-curated allowlists)."""
from __future__ import annotations

from typing import Any, Dict, List, Set

import networkx as nx

from src.cpg._01_cpg_builder import NODE_FUNC, CodePropertyGraphBuilder


class InheritanceClosureGate:
    """Withholds protocol methods of classes inheriting out-of-corpus bases.

    A class inheriting from an unseen base (e.g. stdlib Handler, SQLAlchemy
    TypeEngine) participates in a protocol owned by unanalyzed code, which may
    dispatch to any method by a name absent from the corpus. Withholding is
    one-directional: it can only remove certificates, never create them.
    """

    def __init__(self, graph: nx.DiGraph[Any]) -> None:
        """Bind the gate to a built code property graph."""
        self._graph = graph

    def withheld_methods(self) -> Dict[str, str]:
        """Map each withheld method node id to its human-readable reason."""
        external = CodePropertyGraphBuilder.out_of_corpus_bases(self._graph)
        owners: Set[str] = set(external)
        out: Dict[str, str] = {}
        for n, d in self._graph.nodes(data=True):
            if d.get("kind") == NODE_FUNC and d.get("owner") in owners:
                out[str(n)] = f"inherits out-of-corpus base {external[str(d['owner'])]}"
        return out

    def certified_dead(self, predicted: List[str]) -> List[str]:
        """Filter predicted-dead symbols through the closure witness."""
        withheld = set(self.withheld_methods())
        return [s for s in predicted if s not in withheld]
