"""Deterministic, valid-by-construction diagrams + handbook from the CPG.

Used for golden demos and as the guaranteed fallback when LLM diagrams fail
validation, so the canvas is never blank and never shows a syntax error.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from typing import Any, Dict, List, Tuple

import networkx as nx

from src.cpg._01_cpg_builder import EDGE_CALLS, EDGE_INSTANTIATES, NODE_CLASS, NODE_FILE, NODE_FUNC


class CPGDiagramCompiler:
    """Compiles deterministic HLD/LLD/flow diagrams and handbooks from a CPG."""

    def __init__(self, graph: nx.DiGraph[Any]) -> None:
        """Bind the compiler to a built code property graph."""
        self._graph = graph

    @staticmethod
    def _sid(raw: str, prefix: str = "n") -> str:
        """Sanitize text into a Mermaid-safe node id."""
        clean = re.sub(r"[^A-Za-z0-9]", "_", raw).strip("_")[:40]
        return f"{prefix}_{clean}" if clean else prefix

    @staticmethod
    def _label(raw: str) -> str:
        """Strip Mermaid-hostile characters from a display label."""
        return re.sub(r"[\[\](){}<>\"'`|#;]", " ", raw).strip()[:34] or "node"

    @staticmethod
    def _group(path: str) -> str:
        """Group a file path into its parent package directory."""
        parts = [p for p in path.split("/") if p]
        return "/".join(parts[-3:-1]) if len(parts) > 1 else "root"

    def _call_edges(self) -> List[Tuple[str, str]]:
        """List call/instantiation edges as (src, dst) pairs."""
        return [
            (u, v)
            for u, v, d in self._graph.edges(data=True)
            if d.get("kind") in (EDGE_CALLS, EDGE_INSTANTIATES)
        ]

    def hld(self, limit: int = 12) -> str:
        """Compile a package-level component map with weighted dependencies."""
        g = self._graph
        paths = [str(d["path"]) for _, d in g.nodes(data=True) if d.get("kind") == NODE_FILE]
        groups = Counter(self._group(p) for p in paths)
        by_file = len(groups) < 3
        key = (lambda p: os.path.splitext(os.path.basename(p))[0]) if by_file else self._group
        deps: Counter[Tuple[str, str]] = Counter()
        weight: Counter[str] = Counter()
        for u, v in self._call_edges():
            a, b = key(str(g.nodes[u].get("path") or "")), key(str(g.nodes[v].get("path") or ""))
            weight[a] += 1
            weight[b] += 1
            if a and b and a != b:
                deps[(a, b)] += 1
        for p in paths:
            weight[key(p)] += 0
        top_edges = [(ab, w) for ab, w in deps.most_common(22)]
        top: List[str] = []
        for (a, b), _w in top_edges:
            for k in (a, b):
                if k not in top and len(top) < limit:
                    top.append(k)
        for k, _ in weight.most_common(limit):
            if len(top) >= max(4, min(limit, len(weight))) or k in top:
                continue
            if len(top) < 4:
                top.append(k)
        counts = Counter(key(p) for p in paths)
        hubs = {k for k, _ in weight.most_common(3)}
        lines = ["flowchart LR"]
        for k in top:
            unit = "module" if by_file else f"{counts[k]} files"
            lines.append(f'    {self._sid(k, "c")}["{self._label(k)}<br/><small>{unit}</small>"]')
        for (a, b), w in top_edges:
            if a in top and b in top:
                lines.append(f"    {self._sid(a, 'c')} -->|{w}| {self._sid(b, 'c')}")
        if len(lines) == 1:
            lines.append('    c_root["repository"]')
        lines.append("    classDef hub fill:#0c4a6e,stroke:#38bdf8,stroke-width:2px,color:#f1f5f9")
        lines.append("    classDef mod fill:#1e293b,stroke:#475569,color:#e2e8f0")
        for k in top:
            lines.append(f"    class {self._sid(k, 'c')} {'hub' if k in hubs else 'mod'}")
        return "\n".join(lines)

    def lld(self, limit: int = 8) -> str:
        """Compile a class diagram of the most connected classes."""
        g = self._graph
        ranked: List[Tuple[int, str]] = []
        for n, d in g.nodes(data=True):
            if d.get("kind") == NODE_CLASS:
                ranked.append((g.in_degree(n) + g.out_degree(n), n))
        ranked.sort(reverse=True)
        chosen = [n for _, n in ranked[:limit]]
        names = {n: self._sid(str(g.nodes[n]["name"]), "K") for n in chosen}
        lines = ["classDiagram"]
        for n in chosen:
            methods = [
                str(g.nodes[s]["name"]).split(".")[-1]
                for s in g.successors(n)
                if g.nodes[s].get("kind") == NODE_FUNC
            ]
            public = [m for m in methods if not m.startswith("_")][:6]
            lines.append(f'    class {names[n]}["{self._label(str(g.nodes[n]["name"]))}"] {{')
            for m in public:
                lines.append(f"        +{re.sub(r'[^A-Za-z0-9_]', '', m)}()")
            lines.append("    }")
        for n in chosen:
            for base in g.successors(n):
                if base in names and g.edges[n, base].get("kind") == "INHERITS":
                    lines.append(f"    {names[base]} <|-- {names[n]}")
        if len(lines) == 1:
            lines += ["    class K_module {", "        +main()", "    }"]
        return "\n".join(lines)

    def flow(self, steps: int = 9) -> str:
        """Compile a sequence of the hottest call chain from the best entry point."""
        g = self._graph
        edges = self._call_edges()
        out: Dict[str, List[str]] = {}
        for u, v in edges:
            out.setdefault(u, []).append(v)
        entries = [n for n in out if g.nodes[n].get("kind") in (NODE_FUNC, NODE_FILE)]
        entries.sort(key=lambda n: (-self._cross(n, out), -len(out.get(n, [])), str(n)))
        lines = ["sequenceDiagram", "    autonumber"]
        if not entries:
            return "\n".join(
                lines
                + [
                    "    participant CLI as Entry",
                    "    participant Core as Core engine",
                    "    CLI->>Core: run()",
                    "    Core-->>CLI: result",
                ]
            )
        parts: Dict[str, str] = {}
        cur, seen, count = entries[0], {entries[0]}, 0
        stack = [cur]
        while stack and count < steps:
            cur = stack.pop()
            cands = [v for v in out.get(cur, []) if v not in seen]
            cands.sort(key=lambda v: self._owner(v) == self._owner(cur))
            nxt = cands[:2]
            for v in nxt:
                seen.add(v)
                leaf = self._label(str(g.nodes[v].get("name", "call")).split(".")[-1])
                src_part = self._part(cur, parts, lines)
                dst_part = self._part(v, parts, lines)
                lines.append(f"    {src_part}->>{dst_part}: {leaf}()")
                count += 1
                stack.insert(0, v)
        if count == 0:
            solo = self._part(cur, parts, lines)
            lines.append(f"    {solo}->>{solo}: run()")
        return "\n".join(lines)

    def _home(self, node: str) -> str:
        """Resolve a node to its owning class or file path."""
        name = str(self._graph.nodes[node].get("name") or "")
        if "." in name and self._graph.nodes[node].get("kind") == NODE_FUNC:
            return name.split(".", 1)[0]
        return str(self._graph.nodes[node].get("path") or "")

    def _cross(self, n: str, out: Dict[str, List[str]]) -> int:
        """Count calls from a node into other homes (cross-module fan-out)."""
        return sum(1 for v in out.get(n, []) if self._home(v) != self._home(n))

    def _owner(self, node: str) -> str:
        """Resolve a node to its participant module for sequence diagrams."""
        name = str(self._graph.nodes[node].get("name") or "")
        if "." in name:
            return name.split(".", 1)[0]
        return os.path.splitext(os.path.basename(str(self._graph.nodes[node].get("path") or "mod")))[0]

    def _part(self, node: str, parts: Dict[str, str], lines: List[str]) -> str:
        """Register and return the sequence participant id for a node."""
        mod = self._owner(node)
        if mod not in parts:
            parts[mod] = self._sid(mod, "P")
            lines.insert(2 + len(parts) - 1, f"    participant {parts[mod]} as {self._label(mod)}")
        return parts[mod]

    def handbook(self, name: str, description: str, invariants: List[Dict[str, Any]]) -> str:
        """Compile a chapter-wise markdown handbook purely from the graph."""
        g = self._graph
        files = [d for _, d in g.nodes(data=True) if d.get("kind") == NODE_FILE]
        classes = [
            (g.in_degree(n), str(d["name"]), str(d["path"]))
            for n, d in g.nodes(data=True)
            if d.get("kind") == NODE_CLASS
        ]
        funcs = [n for n, d in g.nodes(data=True) if d.get("kind") == NODE_FUNC]
        hot = sorted(((g.in_degree(n), str(g.nodes[n]["name"])) for n in funcs), reverse=True)[:8]
        groups = Counter(self._group(str(d["path"])) for d in files)
        cycles = [c for c in nx.strongly_connected_components(g) if len(c) > 1]
        classes.sort(reverse=True)
        ch = [
            f"# {name}",
            "",
            "## Executive Summary",
            f"{description}. The analyzed slice spans **{len(files)} files**, **{len(classes)} classes** and "
            f"**{len(funcs)} functions/methods**, connected by **{g.number_of_edges()} structural edges**.",
            "",
            "## Package Purpose",
            *[f"- `{k}` — {v} files" for k, v in groups.most_common(8)],
            "",
            "## Core Components",
            *[f"- **{n}** (`{p}`) — referenced {deg}×" for deg, n, p in classes[:10]],
            "",
            "## Data & Execution Lifecycle",
            "The most depended-on entry points (highest fan-in) carry the runtime:",
            *[f"- `{n}` — {deg} inbound call(s)" for deg, n in hot],
            "",
            "## Scalability Considerations",
            f"- {len(cycles)} dependency cycle group(s) detected; cycles resist modular extraction.",
            f"- Hotspot `{hot[0][1] if hot else 'n/a'}` concentrates coupling — change it with the blast-radius tracer first.",
            "",
            "## Governance Report",
            *[f"- {'✅' if r['passed'] else '❌'} `{r['id']}`" for r in invariants],
        ]
        return "\n".join(ch)
