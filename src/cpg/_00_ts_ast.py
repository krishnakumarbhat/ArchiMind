"""Tree-sitter symbol extraction for Python, stdlib-ast fallback.

Purpose: produce per-module symbols (classes, functions, imports, call sites)
without dumping file text into an LLM context window.
"""
import ast
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModuleSymbols:
    """Symbols extracted from one source file."""

    path: str
    classes: Dict[str, List[str]] = field(default_factory=dict)  # class -> base names
    functions: List[str] = field(default_factory=list)  # module-level defs
    methods: Dict[str, List[str]] = field(default_factory=dict)  # class -> methods
    imports: Dict[str, str] = field(default_factory=dict)  # local name -> module
    calls: List[str] = field(default_factory=list)  # callee leaf names
    attr_calls: List[str] = field(default_factory=list)  # obj.attr leaves (unresolved)
    parse_ok: bool = True


def _extract_ast(source: str, path: str) -> ModuleSymbols:
    syms = ModuleSymbols(path=path)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        syms.parse_ok = False
        return syms
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            syms.classes[node.name] = [
                b.attr if isinstance(b, ast.Attribute) else getattr(b, "id", "?") for b in node.bases
            ]
            syms.methods[node.name] = [
                n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
        elif isinstance(node, ast.ImportFrom) and node.module:
            for a in node.names:
                syms.imports[a.asname or a.name.split(".")[0]] = node.module
        elif isinstance(node, ast.Import):
            for a in node.names:
                syms.imports[a.asname or a.name.split(".")[0]] = a.name
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                syms.calls.append(f.id)
            elif isinstance(f, ast.Attribute):
                syms.calls.append(f.attr)
                syms.attr_calls.append(f.attr)
    syms.functions = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return syms


_QUERY_DEFS = "(class_definition name: (identifier) @cls) (function_definition name: (identifier) @fn)"
_QUERY_CALLS = "(call function: (_) @callee)"


def _extract_treesitter(source: str, path: str) -> Optional[ModuleSymbols]:
    try:
        import tree_sitter_python as tsp
        from tree_sitter import Language, Parser, Query, QueryCursor
    except Exception as exc:  # ponytail: optional accel; stdlib fallback below
        logger.debug("tree-sitter unavailable: %s", exc)
        return None
    try:
        lang = Language(tsp.language())
        parser = Parser(lang)
        tree = parser.parse(source.encode("utf-8", "replace"))
    except Exception as exc:
        logger.warning("tree-sitter parse failed for %s: %s", path, exc)
        return None
    syms = ModuleSymbols(path=path)
    src = source.encode("utf-8", "replace")
    syms.parse_ok = not tree.root_node.has_error

    def text(node: Any) -> str:
        return src[node.start_byte : node.end_byte].decode("utf-8", "replace")

    defs = QueryCursor(Query(lang, _QUERY_DEFS)).captures(tree.root_node)
    for cap_name, nodes in defs.items():
        for node in nodes:
            parent = node.parent
            name = text(node)
            if cap_name == "cls" and parent is not None and parent.type == "class_definition":
                args = [c for c in parent.children if c.type == "argument_list"]
                bases = [
                    text(a).strip("()").split(",")[0].strip().split(".")[-1]
                    for a in args
                    if text(a).strip("()")
                ]
                syms.classes[name] = bases
                syms.methods[name] = []
            elif cap_name == "fn":
                # walk up: identifier -> function_definition -> [block] -> module|class
                p = parent
                while p is not None and p.type in ("function_definition", "block", "decorated_definition"):
                    p = p.parent
                if p is not None and p.type == "module":
                    syms.functions.append(name)
                elif p is not None and p.type == "class_definition":
                    cls_node = p.child_by_field_name("name")
                    cls = text(cls_node) if cls_node is not None else "?"
                    syms.methods.setdefault(cls, []).append(name)
                    syms.classes.setdefault(cls, [])

    calls = QueryCursor(Query(lang, _QUERY_CALLS)).captures(tree.root_node)
    for nodes in calls.values():
        for node in nodes:
            raw = text(node)
            leaf = raw.split(".")[-1].split("(")[0]
            if leaf.isidentifier():
                syms.calls.append(leaf)
                if "." in raw:
                    syms.attr_calls.append(leaf)

    # imports via stdlib (exact, cheap) — tree-sitter import query adds nothing here
    ref = _extract_ast(source, path)
    syms.imports = ref.imports
    if not syms.parse_ok and ref.parse_ok is False:
        syms.parse_ok = False
    return syms


def extract_module(source: str, path: str) -> ModuleSymbols:
    """Extract symbols, preferring tree-sitter, falling back to stdlib ast."""
    ts = _extract_treesitter(source, path)
    if ts is not None:
        return ts
    return _extract_ast(source, path)
