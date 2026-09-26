"""Base-class inheritance closure gate (no hand-curated allowlists)."""
from typing import Any, Dict, List, Set

import networkx as nx

from src.cpg._01_cpg_builder import NODE_FUNC, out_of_corpus_bases


def withheld_methods(g: nx.DiGraph[Any]) -> Dict[str, str]:
    """Method node id -> reason, for methods of classes with out-of-corpus bases.

    A class inheriting from an unseen base (e.g. stdlib Handler, SQLAlchemy
    TypeEngine) participates in a protocol owned by unanalyzed code, which may
    dispatch to any method by a name absent from the corpus. Withholding is
    one-directional: it can only remove certificates, never create them.
    """
    external = out_of_corpus_bases(g)
    owners: Set[str] = set(external)
    out: Dict[str, str] = {}
    for n, d in g.nodes(data=True):
        if d.get("kind") == NODE_FUNC and d.get("owner") in owners:
            out[str(n)] = f"inherits out-of-corpus base {external[str(d['owner'])]}"
    return out


def certified_dead(predicted: List[str], g: nx.DiGraph[Any]) -> List[str]:
    """Filter predicted-dead symbols through the closure witness."""
    withheld = set(withheld_methods(g))
    return [s for s in predicted if s not in withheld]
