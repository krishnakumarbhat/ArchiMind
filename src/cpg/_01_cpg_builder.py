"""NetworkX Code Property Graph: builder, queries, serialization."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Set

import networkx as nx

from src.config._01_constants import DUNDER_EXEMPT_BASE
from src.cpg._00_ts_ast import ModuleSymbols, extract_module

logger = logging.getLogger(__name__)

NODE_FILE, NODE_CLASS, NODE_FUNC = "File", "Class", "Function"
EDGE_IMPORTS, EDGE_CALLS, EDGE_DEFINES, EDGE_INHERITS = "IMPORTS", "CALLS", "DEFINES", "INHERITS"


def _qid(*parts: str) -> str:
    return "::".join(parts)


def build_graph(files: Dict[str, str]) -> nx.DiGraph[Any]:
    """Build typed CPG from {path: source}. Nodes File/Class/Function."""
    mods = {p: extract_module(s, p) for p, s in files.items()}
    g = nx.DiGraph()
    for path, m in mods.items():
        g.add_node(_qid("f", path), kind=NODE_FILE, path=path, parse_ok=m.parse_ok)
        for cls, bases in m.classes.items():
            q = _qid("c", path, cls)
            g.add_node(q, kind=NODE_CLASS, path=path, name=cls, bases=bases)
            g.add_edge(_qid("f", path), q, kind=EDGE_DEFINES)
            for b in bases:
                if b and b != "?":
                    g.add_edge(q, _qid("ext", b), kind=EDGE_INHERITS)
        for fn in m.functions:
            q = _qid("fn", path, fn)
            g.add_node(q, kind=NODE_FUNC, path=path, name=fn)
            g.add_edge(_qid("f", path), q, kind=EDGE_DEFINES)
        for cls, methods in m.methods.items():
            for meth in methods:
                q = _qid("m", path, cls, meth)
                g.add_node(q, kind=NODE_FUNC, path=path, name=f"{cls}.{meth}", owner=cls)
                g.add_edge(_qid("c", path, cls), q, kind=EDGE_DEFINES)
    # CALLS: resolve leaf to module-level defs/methods with that leaf name
    index: Dict[str, List[str]] = {}
    for n, d in g.nodes(data=True):
        if d.get("kind") == NODE_FUNC:
            index.setdefault(str(d["name"]).split(".")[-1], []).append(str(n))
    for path, m in mods.items():
        callers = [_qid("f", path)]
        callers += [_qid("fn", path, f) for f in m.functions]
        for cls, methods in m.methods.items():
            callers += [_qid("m", path, cls, mt) for mt in methods]
        for leaf in m.calls:
            for caller in callers:
                if caller not in g:
                    continue
                for target in index.get(leaf, []):
                    if target != caller:
                        g.add_edge(caller, target, kind=EDGE_CALLS)
    logger.info("CPG: %d nodes, %d edges over %d files", g.number_of_nodes(), g.number_of_edges(), len(files))
    return g


def blast_radius(g: nx.DiGraph[Any], symbol: str) -> List[str]:
    """Downstream symbols reachable from any node whose name matches symbol."""
    roots = [n for n, d in g.nodes(data=True) if d.get("name") == symbol or str(n).endswith("::" + symbol)]
    seen: Set[str] = set()
    stack = list(roots)
    while stack:
        n = stack.pop()
        for succ in g.successors(n):
            if succ not in seen and succ not in roots:
                seen.add(succ)
                stack.append(succ)
    return sorted(seen)


def out_of_corpus_bases(g: nx.DiGraph[Any]) -> Dict[str, List[str]]:
    """Class -> bases with no in-corpus definition (inheritance witness)."""
    defined = {str(d.get("name")) for _, d in g.nodes(data=True) if d.get("kind") == NODE_CLASS}
    result: Dict[str, List[str]] = {}
    for n, d in g.nodes(data=True):
        if d.get("kind") != NODE_CLASS:
            continue
        external = [b for b in d.get("bases", []) if b and b not in defined and b != DUNDER_EXEMPT_BASE]
        if external:
            result[str(d["name"])] = external
    return result


def to_compact(g: nx.DiGraph[Any]) -> Dict[str, Any]:
    """JSON-serializable artifact for status payloads, cache, and API."""
    return {
        "nodes": [
            {"id": n, "kind": d.get("kind"), "name": d.get("name"), "path": d.get("path")}
            for n, d in g.nodes(data=True)
        ],
        "edges": [{"src": u, "dst": v, "kind": d.get("kind")} for u, v, d in g.edges(data=True)],
    }


def from_compact(doc: Dict[str, Any]) -> nx.DiGraph[Any]:
    """Rebuild graph from a compact artifact."""
    g = nx.DiGraph()
    for n in doc.get("nodes", []):
        g.add_node(n["id"], kind=n.get("kind"), name=n.get("name"), path=n.get("path"))
    for e in doc.get("edges", []):
        g.add_edge(e["src"], e["dst"], kind=e.get("kind"))
    return g
