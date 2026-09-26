"""Context-scoped technical handbook builder (CPG-grounded prompt context)."""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict

import networkx as nx

logger = logging.getLogger(__name__)


def cpg_context_block(g: nx.DiGraph[Any], char_limit: int = 6000) -> str:
    """Compact deterministic architecture summary for the doc-generation prompt."""
    from src.cpg._01_cpg_builder import EDGE_CALLS, EDGE_INHERITS, NODE_CLASS, NODE_FILE, NODE_FUNC

    files = sorted(d["path"] for _, d in g.nodes(data=True) if d.get("kind") == NODE_FILE)
    classes = sorted(str(d["name"]) for _, d in g.nodes(data=True) if d.get("kind") == NODE_CLASS)
    edges = [
        f"{g.nodes[u].get('name', u)} -[{d.get('kind')}]-> {g.nodes[v].get('name', v)}"
        for u, v, d in g.edges(data=True)
        if d.get("kind") in (EDGE_CALLS, EDGE_INHERITS)
    ]
    funcs = sum(1 for _, d in g.nodes(data=True) if d.get("kind") == NODE_FUNC)
    block = (
        f"FILES ({len(files)}): " + ", ".join(files[:60]) + "\n"
        f"CLASSES ({len(classes)}): " + ", ".join(classes[:80]) + "\n"
        f"FUNCTIONS: {funcs}\nARCHITECTURE EDGES:\n" + "\n".join(edges[:200])
    )
    return block[:char_limit]


SynthesizeFn = Callable[[str, str], Dict[str, str]]  # (context, repo) -> docs


def synthesize(context: str, repo_name: str, graph: nx.DiGraph[Any], fn: SynthesizeFn) -> Dict[str, str]:
    """Prepend the deterministic CPG block, then delegate to the LLM synthesizer."""
    grounded = cpg_context_block(graph) + "\n\nRETRIEVED CONTEXT:\n" + context
    return fn(grounded, repo_name)
