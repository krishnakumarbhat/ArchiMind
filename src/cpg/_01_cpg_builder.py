"""NetworkX Code Property Graph: builder, queries, serialization.

Edges: DEFINES (file->class/function, class->method), CALLS (scope->callee),
INSTANTIATES (scope->class), INHERITS (class->base). Resolution prefers
precision: self/this calls bind to the owning class, same-file targets win,
imported names narrow the candidate files, and ambiguous leaves (>3 targets)
are refused rather than guessed.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Set

import networkx as nx

from src.config._01_constants import DUNDER_EXEMPT_BASE
from src.cpg._00_ts_ast import ModuleSymbols, extract_module

logger = logging.getLogger(__name__)

NODE_FILE, NODE_CLASS, NODE_FUNC = "File", "Class", "Function"
EDGE_IMPORTS, EDGE_CALLS, EDGE_DEFINES, EDGE_INHERITS = "IMPORTS", "CALLS", "DEFINES", "INHERITS"
EDGE_INSTANTIATES = "INSTANTIATES"
IMPACT_EDGES = frozenset({EDGE_CALLS, EDGE_INSTANTIATES, EDGE_INHERITS})
MAX_AMBIGUOUS = 3


def _qid(*parts: str) -> str:
    return "::".join(parts)


def _stem(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def _import_stem(module: str) -> str:
    """'./foo.js' -> 'foo' (path import); 'a.b.c' -> 'c' (dotted import)."""
    tail = module.rstrip("/").split("/")[-1]
    if "/" in module or module.startswith("."):
        return os.path.splitext(tail)[0]
    return tail.split(".")[-1]


def _scope_node(path: str, scope: str, m: ModuleSymbols) -> str:
    if not scope:
        return _qid("f", path)
    if "." in scope:
        cls, meth = scope.split(".", 1)
        return _qid("m", path, cls, meth)
    return _qid("fn", path, scope)


def build_graph(files: Dict[str, str]) -> nx.DiGraph[Any]:
    """Build typed CPG from {path: source}."""
    mods = {p: extract_module(s, p) for p, s in files.items()}
    g: nx.DiGraph[Any] = nx.DiGraph()
    funcs: Dict[str, List[str]] = {}
    classes: Dict[str, List[str]] = {}
    for path, m in mods.items():
        g.add_node(_qid("f", path), kind=NODE_FILE, path=path, name=path, parse_ok=m.parse_ok)
        for cls, bases in m.classes.items():
            q = _qid("c", path, cls)
            g.add_node(q, kind=NODE_CLASS, path=path, name=cls, bases=bases)
            g.add_edge(_qid("f", path), q, kind=EDGE_DEFINES)
            classes.setdefault(cls, []).append(q)
        for fn in m.functions:
            q = _qid("fn", path, fn)
            g.add_node(q, kind=NODE_FUNC, path=path, name=fn)
            g.add_edge(_qid("f", path), q, kind=EDGE_DEFINES)
            funcs.setdefault(fn, []).append(q)
        for cls, methods in m.methods.items():
            for meth in methods:
                q = _qid("m", path, cls, meth)
                g.add_node(q, kind=NODE_FUNC, path=path, name=f"{cls}.{meth}", owner=cls)
                g.add_edge(_qid("c", path, cls), q, kind=EDGE_DEFINES)
                funcs.setdefault(meth, []).append(q)
    for path, m in mods.items():
        for cls, bases in m.classes.items():
            for b in bases:
                if not b or b == "?":
                    continue
                targets = classes.get(b) or [_qid("ext", b)]
                for t in targets[:MAX_AMBIGUOUS]:
                    if t not in g:
                        g.add_node(t, kind="External", name=b, path="")
                    g.add_edge(_qid("c", path, cls), t, kind=EDGE_INHERITS)
        imported_stems = {_import_stem(v) for v in m.imports.values()}
        for scope, leaf, receiver in m.scoped_calls:
            caller = _scope_node(path, scope, m)
            if caller not in g:
                continue
            owner = scope.split(".", 1)[0] if "." in scope else ""
            if receiver in ("self", "this", "cls") and owner and leaf in m.methods.get(owner, []):
                g.add_edge(caller, _qid("m", path, owner, leaf), kind=EDGE_CALLS)
                continue
            kind = EDGE_INSTANTIATES if leaf in classes else EDGE_CALLS
            cands = classes.get(leaf, []) if kind == EDGE_INSTANTIATES else funcs.get(leaf, [])
            cands = [c for c in cands if c != caller]
            if not cands:
                continue
            local = [c for c in cands if g.nodes[c]["path"] == path]
            if local:
                cands = local
            elif leaf in m.imports or receiver in m.imports:
                narrowed = [c for c in cands if _stem(g.nodes[c]["path"]) in imported_stems]
                cands = narrowed or cands
            if len(cands) > MAX_AMBIGUOUS:
                continue  # ponytail: refuse to guess; research showed guessing kills precision
            for c in cands:
                g.add_edge(caller, c, kind=kind)
    logger.info("CPG: %d nodes, %d edges over %d files", g.number_of_nodes(), g.number_of_edges(), len(files))
    return g


def _roots(g: nx.DiGraph[Any], symbol: str) -> List[str]:
    sym = symbol.strip()
    exact = [n for n, d in g.nodes(data=True) if d.get("name") == sym]
    if exact:
        return exact
    leaf = sym.split(".")[-1]
    return [n for n, d in g.nodes(data=True) if str(d.get("name", "")).split(".")[-1] == leaf]


def blast_radius(g: nx.DiGraph[Any], symbol: str) -> List[str]:
    """Everything affected if `symbol` changes: transitive callers/instantiators/subclasses."""
    roots = _roots(g, symbol)
    seen: Set[str] = set()
    stack = list(roots)
    while stack:
        n = stack.pop()
        for pred in g.predecessors(n):
            if g.edges[pred, n].get("kind") in IMPACT_EDGES and pred not in seen and pred not in roots:
                seen.add(pred)
                stack.append(pred)
    return sorted(seen)


def out_of_corpus_bases(g: nx.DiGraph[Any]) -> Dict[str, List[str]]:
    """Class -> bases with no in-corpus definition (inheritance witness)."""
    defined = {str(d.get("name")) for _, d in g.nodes(data=True) if d.get("kind") == NODE_CLASS}
    result: Dict[str, List[str]] = {}
    for _, d in g.nodes(data=True):
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
    g: nx.DiGraph[Any] = nx.DiGraph()
    for n in doc.get("nodes", []):
        g.add_node(n["id"], kind=n.get("kind"), name=n.get("name"), path=n.get("path"))
    for e in doc.get("edges", []):
        g.add_edge(e["src"], e["dst"], kind=e.get("kind"))
    return g
