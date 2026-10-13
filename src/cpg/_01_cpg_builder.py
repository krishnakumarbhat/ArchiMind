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
from src.cpg._00_ts_ast import ASTExtractor, ModuleSymbols

logger = logging.getLogger(__name__)

NODE_FILE, NODE_CLASS, NODE_FUNC = "File", "Class", "Function"
EDGE_IMPORTS, EDGE_CALLS, EDGE_DEFINES, EDGE_INHERITS = "IMPORTS", "CALLS", "DEFINES", "INHERITS"
EDGE_INSTANTIATES = "INSTANTIATES"
IMPACT_EDGES = frozenset({EDGE_CALLS, EDGE_INSTANTIATES, EDGE_INHERITS})
MAX_AMBIGUOUS = 3


class CodePropertyGraphBuilder:
    """Constructs and queries a typed NetworkX code property graph."""

    def __init__(self, extractor: ASTExtractor | None = None) -> None:
        """Create a builder sharing one cached AST extractor."""
        self._extractor = extractor or ASTExtractor()

    @staticmethod
    def _qid(*parts: str) -> str:
        """Join path fragments into a stable node id."""
        return "::".join(parts)

    @staticmethod
    def _stem(path: str) -> str:
        """Strip directories and extension from a path."""
        return os.path.splitext(os.path.basename(path))[0]

    @staticmethod
    def _import_stem(module: str) -> str:
        """Normalize an import target for file matching."""
        tail = module.rstrip("/").split("/")[-1]
        if "/" in module or module.startswith("."):
            return os.path.splitext(tail)[0]
        return tail.split(".")[-1]

    @classmethod
    def _scope_node(cls, path: str, scope: str) -> str:
        """Map a lexical scope to its graph node id."""
        if not scope:
            return cls._qid("f", path)
        if "." in scope:
            owner, meth = scope.split(".", 1)
            return cls._qid("m", path, owner, meth)
        return cls._qid("fn", path, scope)

    def build(self, files: Dict[str, str]) -> nx.DiGraph[Any]:
        """Build a typed CPG from a {path: source} mapping."""
        mods = {p: self._extractor.extract_module(s, p) for p, s in files.items()}
        g: nx.DiGraph[Any] = nx.DiGraph()
        funcs: Dict[str, List[str]] = {}
        classes: Dict[str, List[str]] = {}
        for path, m in mods.items():
            self._declare(path, m, g, funcs, classes)
        for path, m in mods.items():
            self._link_inheritance(path, m, g, classes)
            self._link_calls(path, m, g, funcs, classes)
        logger.info(
            "CPG: %d nodes, %d edges over %d files", g.number_of_nodes(), g.number_of_edges(), len(files)
        )
        return g

    def _declare(
        self,
        path: str,
        m: ModuleSymbols,
        g: nx.DiGraph[Any],
        funcs: Dict[str, List[str]],
        classes: Dict[str, List[str]],
    ) -> None:
        """Add file/class/function/method nodes and DEFINES edges."""
        g.add_node(self._qid("f", path), kind=NODE_FILE, path=path, name=path, parse_ok=m.parse_ok)
        for cls in m.classes:
            q = self._qid("c", path, cls)
            g.add_node(q, kind=NODE_CLASS, path=path, name=cls, bases=m.classes[cls])
            g.add_edge(self._qid("f", path), q, kind=EDGE_DEFINES)
            classes.setdefault(cls, []).append(q)
        for fn in m.functions:
            q = self._qid("fn", path, fn)
            g.add_node(q, kind=NODE_FUNC, path=path, name=fn)
            g.add_edge(self._qid("f", path), q, kind=EDGE_DEFINES)
            funcs.setdefault(fn, []).append(q)
        for cls, methods in m.methods.items():
            for meth in methods:
                q = self._qid("m", path, cls, meth)
                g.add_node(q, kind=NODE_FUNC, path=path, name=f"{cls}.{meth}", owner=cls)
                g.add_edge(self._qid("c", path, cls), q, kind=EDGE_DEFINES)
                funcs.setdefault(meth, []).append(q)

    def _link_inheritance(
        self, path: str, m: ModuleSymbols, g: nx.DiGraph[Any], classes: Dict[str, List[str]]
    ) -> None:
        """Add INHERITS edges from classes to their resolved bases."""
        for cls, bases in m.classes.items():
            for b in bases:
                if not b or b == "?":
                    continue
                targets = classes.get(b) or [self._qid("ext", b)]
                for t in targets[:MAX_AMBIGUOUS]:
                    if t not in g:
                        g.add_node(t, kind="External", name=b, path="")
                    g.add_edge(self._qid("c", path, cls), t, kind=EDGE_INHERITS)

    def _link_calls(
        self,
        path: str,
        m: ModuleSymbols,
        g: nx.DiGraph[Any],
        funcs: Dict[str, List[str]],
        classes: Dict[str, List[str]],
    ) -> None:
        """Resolve scoped call sites to CALLS/INSTANTIATES edges."""
        imported_stems = {self._import_stem(v) for v in m.imports.values()}
        for scope, leaf, receiver in m.scoped_calls:
            caller = self._scope_node(path, scope)
            if caller not in g:
                continue
            owner = scope.split(".", 1)[0] if "." in scope else ""
            if receiver in ("self", "this", "cls") and owner and leaf in m.methods.get(owner, []):
                g.add_edge(caller, self._qid("m", path, owner, leaf), kind=EDGE_CALLS)
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
                narrowed = [c for c in cands if self._stem(g.nodes[c]["path"]) in imported_stems]
                cands = narrowed or cands
            if len(cands) > MAX_AMBIGUOUS:
                continue  # ponytail: refuse to guess; research showed guessing kills precision
            for c in cands:
                g.add_edge(caller, c, kind=kind)

    @staticmethod
    def _roots(g: nx.DiGraph[Any], symbol: str) -> List[str]:
        """Find graph nodes matching a symbol exactly, then by leaf name."""
        sym = symbol.strip()
        exact = [n for n, d in g.nodes(data=True) if d.get("name") == sym]
        if exact:
            return exact
        leaf = sym.split(".")[-1]
        return [n for n, d in g.nodes(data=True) if str(d.get("name", "")).split(".")[-1] == leaf]

    @classmethod
    def blast_radius(cls, g: nx.DiGraph[Any], symbol: str) -> List[str]:
        """List everything affected if `symbol` changes (transitive dependents)."""
        roots = cls._roots(g, symbol)
        seen: Set[str] = set()
        stack = list(roots)
        while stack:
            n = stack.pop()
            for pred in g.predecessors(n):
                if g.edges[pred, n].get("kind") in IMPACT_EDGES and pred not in seen and pred not in roots:
                    seen.add(pred)
                    stack.append(pred)
        return sorted(seen)

    @staticmethod
    def out_of_corpus_bases(g: nx.DiGraph[Any]) -> Dict[str, List[str]]:
        """Map each class to bases with no in-corpus definition."""
        defined = {str(d.get("name")) for _, d in g.nodes(data=True) if d.get("kind") == NODE_CLASS}
        result: Dict[str, List[str]] = {}
        for _, d in g.nodes(data=True):
            if d.get("kind") != NODE_CLASS:
                continue
            external = [b for b in d.get("bases", []) if b and b not in defined and b != DUNDER_EXEMPT_BASE]
            if external:
                result[str(d["name"])] = external
        return result

    @staticmethod
    def to_compact(g: nx.DiGraph[Any]) -> Dict[str, Any]:
        """Serialize a graph to a JSON-safe artifact."""
        return {
            "nodes": [
                {"id": n, "kind": d.get("kind"), "name": d.get("name"), "path": d.get("path")}
                for n, d in g.nodes(data=True)
            ],
            "edges": [{"src": u, "dst": v, "kind": d.get("kind")} for u, v, d in g.edges(data=True)],
        }

    @staticmethod
    def from_compact(doc: Dict[str, Any]) -> nx.DiGraph[Any]:
        """Rebuild a graph from a compact artifact."""
        g: nx.DiGraph[Any] = nx.DiGraph()
        for n in doc.get("nodes", []):
            g.add_node(n["id"], kind=n.get("kind"), name=n.get("name"), path=n.get("path"))
        for e in doc.get("edges", []):
            g.add_edge(e["src"], e["dst"], kind=e.get("kind"))
        return g
