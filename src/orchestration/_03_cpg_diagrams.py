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


def _sid(raw: str, prefix: str = "n") -> str:
    clean = re.sub(r"[^A-Za-z0-9]", "_", raw).strip("_")[:40]
    return f"{prefix}_{clean}" if clean else prefix


def _label(raw: str) -> str:
    return re.sub(r"[\[\](){}<>\"'`|#;]", " ", raw).strip()[:34] or "node"


def _group(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    return "/".join(parts[-3:-1]) if len(parts) > 1 else "root"


def _call_edges(g: nx.DiGraph[Any]) -> List[Tuple[str, str]]:
    return [(u, v) for u, v, d in g.edges(data=True) if d.get("kind") in (EDGE_CALLS, EDGE_INSTANTIATES)]


def hld(g: nx.DiGraph[Any], limit: int = 12) -> str:
    """Package-level (or file-level) component map with weighted dependencies."""
    paths = [str(d["path"]) for _, d in g.nodes(data=True) if d.get("kind") == NODE_FILE]
    groups = Counter(_group(p) for p in paths)
    by_file = len(groups) < 3
    key = (lambda p: os.path.splitext(os.path.basename(p))[0]) if by_file else _group
    deps: Counter[Tuple[str, str]] = Counter()
    weight: Counter[str] = Counter()
    for u, v in _call_edges(g):
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
        lines.append(f'    {_sid(k, "c")}["{_label(k)}<br/><small>{unit}</small>"]')
    for (a, b), w in top_edges:
        if a in top and b in top:
            lines.append(f"    {_sid(a, 'c')} -->|{w}| {_sid(b, 'c')}")
    if len(lines) == 1:
        lines.append('    c_root["repository"]')
    lines.append("    classDef hub fill:#0c4a6e,stroke:#38bdf8,stroke-width:2px,color:#f1f5f9")
    lines.append("    classDef mod fill:#1e293b,stroke:#475569,color:#e2e8f0")
    for k in top:
        lines.append(f"    class {_sid(k, 'c')} {'hub' if k in hubs else 'mod'}")
    return "\n".join(lines)


def lld(g: nx.DiGraph[Any], limit: int = 8) -> str:
    """Class diagram of the most connected classes with public methods."""
    ranked: List[Tuple[int, str]] = []
    for n, d in g.nodes(data=True):
        if d.get("kind") == NODE_CLASS:
            ranked.append((g.in_degree(n) + g.out_degree(n), n))
    ranked.sort(reverse=True)
    chosen = [n for _, n in ranked[:limit]]
    names = {n: _sid(str(g.nodes[n]["name"]), "K") for n in chosen}
    lines = ["classDiagram"]
    for n in chosen:
        methods = [
            str(g.nodes[s]["name"]).split(".")[-1]
            for s in g.successors(n)
            if g.nodes[s].get("kind") == NODE_FUNC
        ]
        public = [m for m in methods if not m.startswith("_")][:6]
        lines.append(f'    class {names[n]}["{_label(str(g.nodes[n]["name"]))}"] {{')
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


def flow(g: nx.DiGraph[Any], steps: int = 9) -> str:
    """Sequence of the hottest call chain from the best entry point."""
    edges = _call_edges(g)
    out: Dict[str, List[str]] = {}
    for u, v in edges:
        out.setdefault(u, []).append(v)
    def home(node: str) -> str:
        name = str(g.nodes[node].get("name") or "")
        if "." in name and g.nodes[node].get("kind") == NODE_FUNC:
            return name.split(".", 1)[0]
        return str(g.nodes[node].get("path") or "")

    def cross(n: str) -> int:
        return sum(1 for v in out.get(n, []) if home(v) != home(n))

    entries = [n for n in out if g.nodes[n].get("kind") in (NODE_FUNC, NODE_FILE)]
    entries.sort(key=lambda n: (-cross(n), -len(out.get(n, [])), str(n)))
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

    def owner(node: str) -> str:
        name = str(g.nodes[node].get("name") or "")
        if "." in name:
            return name.split(".", 1)[0]
        return os.path.splitext(os.path.basename(str(g.nodes[node].get("path") or "mod")))[0]

    def part(node: str) -> str:
        mod = owner(node)
        if mod not in parts:
            parts[mod] = _sid(mod, "P")
            lines.insert(2 + len(parts) - 1, f"    participant {parts[mod]} as {_label(mod)}")
        return parts[mod]

    cur, seen, count = entries[0], {entries[0]}, 0
    stack = [cur]
    while stack and count < steps:
        cur = stack.pop()
        cands = [v for v in out.get(cur, []) if v not in seen]
        cands.sort(key=lambda v: owner(v) == owner(cur))
        nxt = cands[:2]
        for v in nxt:
            seen.add(v)
            leaf = _label(str(g.nodes[v].get("name", "call")).split(".")[-1])
            lines.append(f"    {part(cur)}->>{part(v)}: {leaf}()")
            count += 1
            stack.insert(0, v)
    if count == 0:
        lines.append(f"    {part(cur)}->>{part(cur)}: run()")
    return "\n".join(lines)


def handbook(g: nx.DiGraph[Any], name: str, description: str, invariants: List[Dict[str, Any]]) -> str:
    """Chapter-wise markdown handbook derived purely from the graph."""
    files = [d for _, d in g.nodes(data=True) if d.get("kind") == NODE_FILE]
    classes = [(g.in_degree(n), str(d["name"]), str(d["path"])) for n, d in g.nodes(data=True) if d.get("kind") == NODE_CLASS]
    funcs = [n for n, d in g.nodes(data=True) if d.get("kind") == NODE_FUNC]
    hot = sorted(((g.in_degree(n), str(g.nodes[n]["name"])) for n in funcs), reverse=True)[:8]
    groups = Counter(_group(str(d["path"])) for d in files)
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
