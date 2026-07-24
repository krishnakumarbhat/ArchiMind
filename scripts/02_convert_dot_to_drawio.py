#!/usr/bin/env python3
"""Convert simple Graphviz DOT diagrams into draw.io XML files."""

from __future__ import annotations

import argparse
import html
import re
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from pathlib import Path


ATTR_PATTERN = re.compile(r"(\w+)\s*=\s*(\"(?:[^\"\\]|\\.)*\"|[^,\]]+)")
NODE_PATTERN = re.compile(r"^(?P<name>[A-Za-z0-9_]+)\s*\[(?P<attrs>.+)\]\s*;?$")
EDGE_PATTERN = re.compile(
    r"^(?P<src>[A-Za-z0-9_]+)\s*->\s*(?P<dst>[A-Za-z0-9_]+)\s*(?:\[(?P<attrs>.+)\])?\s*;?$"
)


def parse_attrs(raw_attrs: str) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for match in ATTR_PATTERN.finditer(raw_attrs):
        key = match.group(1)
        value = match.group(2).strip().strip('"')
        value = value.replace(r"\n", "\n").replace(r'\"', '"')
        attributes[key] = value
    return attributes


def parse_dot(dot_path: Path) -> tuple[str, str, dict[str, dict[str, str]], list[dict[str, str]], dict[str, str], dict[str, str]]:
    title = dot_path.stem.replace("_", " ").title()
    rankdir = "LR"
    node_defaults: dict[str, str] = {}
    edge_defaults: dict[str, str] = {}
    nodes: dict[str, dict[str, str]] = {}
    edges: list[dict[str, str]] = []

    for raw_line in dot_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//") or line in {"{", "}"}:
            continue
        if line.startswith("digraph "):
            continue
        if line.startswith("rankdir="):
            rankdir = line.split("=", 1)[1].rstrip(";").strip()
            continue
        if line.startswith("graph ["):
            graph_attrs = parse_attrs(line[line.find("[") + 1 : line.rfind("]")])
            title = graph_attrs.get("label", title)
            continue
        if line.startswith("node ["):
            node_defaults.update(parse_attrs(line[line.find("[") + 1 : line.rfind("]")]))
            continue
        if line.startswith("edge ["):
            edge_defaults.update(parse_attrs(line[line.find("[") + 1 : line.rfind("]")]))
            continue

        edge_match = EDGE_PATTERN.match(line)
        if edge_match:
            attrs = edge_defaults.copy()
            if edge_match.group("attrs"):
                attrs.update(parse_attrs(edge_match.group("attrs")))
            attrs["src"] = edge_match.group("src")
            attrs["dst"] = edge_match.group("dst")
            edges.append(attrs)
            continue

        node_match = NODE_PATTERN.match(line)
        if node_match:
            attrs = node_defaults.copy()
            attrs.update(parse_attrs(node_match.group("attrs")))
            attrs["name"] = node_match.group("name")
            nodes[node_match.group("name")] = attrs

    return title, rankdir, nodes, edges, node_defaults, edge_defaults


def compute_positions(node_names: list[str], edges: list[dict[str, str]], rankdir: str) -> dict[str, tuple[int, int]]:
    if not node_names:
        return {}

    adjacency: dict[str, list[str]] = defaultdict(list)
    indegree = {name: 0 for name in node_names}
    for edge in edges:
        src = edge["src"]
        dst = edge["dst"]
        adjacency[src].append(dst)
        indegree[dst] = indegree.get(dst, 0) + 1

    queue = deque([name for name in node_names if indegree.get(name, 0) == 0] or [node_names[0]])
    depth = {queue[0]: 0}
    visited = set()

    while queue:
        current = queue.popleft()
        visited.add(current)
        for neighbor in adjacency.get(current, []):
            candidate_depth = depth.get(current, 0) + 1
            if candidate_depth > depth.get(neighbor, -1):
                depth[neighbor] = candidate_depth
            if neighbor not in visited:
                queue.append(neighbor)

    current_depth = max(depth.values(), default=0)
    for name in node_names:
        if name not in depth:
            current_depth += 1
            depth[name] = current_depth

    layers: dict[int, list[str]] = defaultdict(list)
    for name in node_names:
        layers[depth[name]].append(name)

    positions: dict[str, tuple[int, int]] = {}
    x_spacing = 260
    y_spacing = 140
    base_x = 60
    base_y = 80

    for layer_index in sorted(layers):
        for slot, name in enumerate(layers[layer_index]):
            if rankdir == "TB":
                x = base_x + slot * x_spacing
                y = base_y + layer_index * y_spacing
            else:
                x = base_x + layer_index * x_spacing
                y = base_y + slot * y_spacing
            positions[name] = (x, y)

    return positions


def node_dimensions(label: str, shape: str) -> tuple[int, int]:
    lines = label.splitlines() or [label]
    max_length = max(len(line) for line in lines) if lines else 16
    width = min(max(150, 8 * max_length + 36), 320)
    height = max(60, 28 + len(lines) * 20)
    if shape in {"circle", "doublecircle"}:
        diameter = max(70, min(120, max(width, height)))
        return diameter, diameter
    return width, height


def html_label(label: str) -> str:
    return html.escape(label).replace("\n", "<br>")


def node_style(attrs: dict[str, str]) -> str:
    shape = attrs.get("shape", "box")
    fill = attrs.get("fillcolor", "#ffffff")
    stroke = attrs.get("color", "#5b6b7a")
    dashed = "dashed=1;" if "dashed" in attrs.get("style", "") else ""

    if shape == "ellipse":
        base = "ellipse;whiteSpace=wrap;html=1;"
    elif shape == "cylinder":
        base = "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;"
    elif shape == "note":
        base = "shape=note;whiteSpace=wrap;html=1;"
    elif shape == "component":
        base = "shape=component;whiteSpace=wrap;html=1;"
    elif shape == "circle":
        base = "ellipse;aspect=fixed;whiteSpace=wrap;html=1;"
    elif shape == "doublecircle":
        base = "shape=doubleEllipse;aspect=fixed;whiteSpace=wrap;html=1;"
    else:
        base = "rounded=1;whiteSpace=wrap;html=1;"

    return f"{base}{dashed}fillColor={fill};strokeColor={stroke};fontColor=#1f2933;"


def edge_style(attrs: dict[str, str]) -> str:
    stroke = attrs.get("color", "#4a6484")
    dashed = "dashed=1;" if "dashed" in attrs.get("style", "") else ""
    return (
        "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;"
        f"{dashed}strokeColor={stroke};"
    )


def build_drawio(dot_path: Path, output_path: Path) -> None:
    title, rankdir, nodes, edges, _, _ = parse_dot(dot_path)
    node_names = list(nodes.keys())
    positions = compute_positions(node_names, edges, rankdir)

    mxfile = ET.Element("mxfile", host="app.diagrams.net", version="28.1.2")
    diagram = ET.SubElement(mxfile, "diagram", name=title)
    graph_model = ET.SubElement(
        diagram,
        "mxGraphModel",
        dx="1200",
        dy="800",
        grid="1",
        gridSize="10",
        guides="1",
        tooltips="1",
        connect="1",
        arrows="1",
        fold="1",
        page="1",
        pageScale="1",
        pageWidth="1600",
        pageHeight="1200",
        math="0",
        shadow="0",
    )
    root = ET.SubElement(graph_model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    cell_ids: dict[str, str] = {}
    next_id = 2

    for name in node_names:
        attrs = nodes[name]
        label = attrs.get("label", name)
        shape = attrs.get("shape", "box")
        width, height = node_dimensions(label, shape)
        x, y = positions.get(name, (60, 80))
        cell_id = str(next_id)
        next_id += 1
        cell_ids[name] = cell_id

        cell = ET.SubElement(
            root,
            "mxCell",
            id=cell_id,
            value=html_label(label),
            style=node_style(attrs),
            vertex="1",
            parent="1",
        )
        ET.SubElement(
            cell,
            "mxGeometry",
            attrib={
                "x": str(x),
                "y": str(y),
                "width": str(width),
                "height": str(height),
                "as": "geometry",
            },
        )

    for edge in edges:
        edge_id = str(next_id)
        next_id += 1
        label = html_label(edge.get("label", ""))
        cell = ET.SubElement(
            root,
            "mxCell",
            id=edge_id,
            value=label,
            style=edge_style(edge),
            edge="1",
            parent="1",
            source=cell_ids[edge["src"]],
            target=cell_ids[edge["dst"]],
        )
        ET.SubElement(cell, "mxGeometry", attrib={"relative": "1", "as": "geometry"})

    tree = ET.ElementTree(mxfile)
    ET.indent(tree, space="  ")
    output_path.write_text(
        ET.tostring(mxfile, encoding="unicode", xml_declaration=False),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("docs/diagrams"),
        help="Directory containing .dot files.",
    )
    args = parser.parse_args()

    input_dir = args.input_dir
    for dot_file in sorted(input_dir.glob("*.dot")):
        output_path = dot_file.with_suffix(".drawio")
        build_drawio(dot_file, output_path)
        print(f"Converted {dot_file} -> {output_path}")


if __name__ == "__main__":
    main()