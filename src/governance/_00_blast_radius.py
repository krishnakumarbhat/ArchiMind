"""Downstream BFS reachability (blast radius) over a compact CPG artifact."""
import time
from typing import Any, Dict, List

from src.cpg._01_cpg_builder import blast_radius, from_compact


def impact(symbol: str, artifact: Dict[str, Any]) -> Dict[str, Any]:
    """Return impacted downstream symbols + timing for a changed symbol."""
    started = time.time()
    g = from_compact(artifact)
    hit = blast_radius(g, symbol)
    names: List[str] = []
    for node_id in hit:
        name = g.nodes[node_id].get("name") or node_id
        if name not in names:
            names.append(str(name))
    return {
        "symbol": symbol,
        "impacted": names,
        "edges": len(names),
        "ms": round((time.time() - started) * 1000, 2),
    }
