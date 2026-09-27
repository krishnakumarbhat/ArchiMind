"""Tree-sitter symbol extraction (Python + TypeScript/JavaScript) with call scopes.

Purpose: per-module classes, functions, methods, imports and *scoped* call sites
(which function makes which call, with its receiver) so the CPG builder can
resolve edges precisely instead of linking every caller in a file to every
same-named target. Tree-sitter is error-tolerant: broken files still yield
symbols, with parse_ok=False.
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

Call = Tuple[str, str, str]  # (scope, callee leaf, receiver text)


@dataclass
class ModuleSymbols:
    """Symbols extracted from one source file."""

    path: str
    classes: Dict[str, List[str]] = field(default_factory=dict)  # class -> base names
    functions: List[str] = field(default_factory=list)  # module-level defs
    methods: Dict[str, List[str]] = field(default_factory=dict)  # class -> methods
    imports: Dict[str, str] = field(default_factory=dict)  # local name -> module
    calls: List[str] = field(default_factory=list)  # callee leaf names (all scopes)
    scoped_calls: List[Call] = field(default_factory=list)
    parse_ok: bool = True


_SPEC: Dict[str, Dict[str, Any]] = {
    "python": {
        "cls": {"class_definition"},
        "fn": {"function_definition"},
        "call": {"call"},
        "member": {"attribute"},
        "member_obj": "object",
        "member_prop": "attribute",
        "call_fn": "function",
    },
    "typescript": {
        "cls": {"class_declaration", "abstract_class_declaration"},
        "fn": {"function_declaration", "method_definition", "generator_function_declaration"},
        "call": {"call_expression", "new_expression"},
        "member": {"member_expression"},
        "member_obj": "object",
        "member_prop": "property",
        "call_fn": "function",
    },
}

_JS_KEYWORDS = {"if", "for", "while", "switch", "catch", "return", "typeof", "super", "import", "require"}


def _language(path: str) -> Optional[str]:
    if path.endswith(".py"):
        return "python"
    if path.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")):
        return "typescript"
    return None


def _parser(lang: str, path: str) -> Any:
    from tree_sitter import Language, Parser

    if lang == "python":
        import tree_sitter_python as tsp

        return Parser(Language(tsp.language()))
    import tree_sitter_typescript as tst

    grammar = tst.language_tsx() if path.endswith((".tsx", ".jsx")) else tst.language_typescript()
    return Parser(Language(grammar))


def _imports(source: str, lang: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if lang == "python":
        for m in re.finditer(r"(?m)^\s*from\s+([\w.]+)\s+import\s+\(?([\w,\s]+)", source):
            for name in m.group(2).split(","):
                name = name.strip().split(" as ")[-1].strip()
                if name:
                    out[name] = m.group(1)
        for m in re.finditer(r"(?m)^\s*import\s+([\w.]+)(?:\s+as\s+(\w+))?", source):
            out[m.group(2) or m.group(1).split(".")[0]] = m.group(1)
        return out
    for m in re.finditer(r"import\s+(?:type\s+)?([^;'\"]+?)\s+from\s+['\"]([^'\"]+)['\"]", source):
        for name in re.findall(r"[A-Za-z_$][\w$]*", m.group(1).replace(" as ", " ")):
            if name not in ("type", "as"):
                out[name] = m.group(2)
    return out


def _extract_treesitter(source: str, path: str) -> Optional[ModuleSymbols]:
    lang = _language(path)
    if lang is None:
        return None
    try:
        parser = _parser(lang, path)
        src = source.encode("utf-8", "replace")
        tree = parser.parse(src)
    except Exception as exc:  # ponytail: grammar missing -> stdlib fallback
        logger.debug("tree-sitter unavailable for %s: %s", path, exc)
        return None
    spec = _SPEC[lang]
    syms = ModuleSymbols(path=path, parse_ok=not tree.root_node.has_error)

    def text(node: Any) -> str:
        return src[node.start_byte : node.end_byte].decode("utf-8", "replace")

    def name_of(node: Any) -> str:
        n = node.child_by_field_name("name")
        return text(n) if n is not None else ""

    # explicit stack: (node, class_name, scope_name)
    stack: List[Tuple[Any, str, str]] = [(tree.root_node, "", "")]
    while stack:
        node, cls, scope = stack.pop()
        t = node.type
        if t in spec["cls"]:
            cname = name_of(node) or cls
            if cname:
                bases: List[str] = []
                if lang == "python":
                    sup = node.child_by_field_name("superclasses")
                    if sup is not None:
                        bases = [b.split(".")[-1] for b in re.findall(r"[\w.]+", text(sup)) if b != "metaclass"]
                else:
                    heritage = next((c for c in node.children if c.type == "class_heritage"), None)
                    if heritage is not None:
                        m = re.search(r"extends\s+([\w.$]+)", text(heritage))
                        bases = [m.group(1).split(".")[-1]] if m else []
                syms.classes[cname] = bases
                syms.methods.setdefault(cname, [])
            for child in reversed(node.children):
                stack.append((child, cname, ""))
            continue
        new_scope = scope
        if t in spec["fn"] or (
            t == "variable_declarator"
            and (v := node.child_by_field_name("value")) is not None
            and v.type in ("arrow_function", "function_expression", "function")
        ):
            fname = name_of(node)
            if fname and not scope:
                if cls:
                    syms.methods.setdefault(cls, []).append(fname)
                    new_scope = f"{cls}.{fname}"
                elif t != "method_definition":
                    syms.functions.append(fname)
                    new_scope = fname
        if t in spec["call"]:
            fn = node.child_by_field_name("constructor" if t == "new_expression" else spec["call_fn"])
            if fn is not None:
                receiver = ""
                if fn.type in spec["member"]:
                    prop = fn.child_by_field_name(spec["member_prop"])
                    obj = fn.child_by_field_name(spec["member_obj"])
                    leaf = text(prop) if prop is not None else ""
                    receiver = text(obj) if obj is not None else ""
                else:
                    leaf = text(fn).split(".")[-1]
                if leaf.isidentifier() and leaf not in _JS_KEYWORDS:
                    syms.calls.append(leaf)
                    syms.scoped_calls.append((scope, leaf, receiver))
        for child in reversed(node.children):
            stack.append((child, cls, new_scope))
    syms.imports = _imports(source, lang)
    return syms


def _extract_ast(source: str, path: str) -> ModuleSymbols:
    """Stdlib fallback for Python when tree-sitter is unavailable."""
    syms = ModuleSymbols(path=path)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        syms.parse_ok = False
        return syms

    def visit(node: ast.AST, cls: str, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                syms.classes[child.name] = [
                    b.attr if isinstance(b, ast.Attribute) else getattr(b, "id", "?") for b in child.bases
                ]
                syms.methods.setdefault(child.name, [])
                visit(child, child.name, "")
                continue
            new_scope = scope
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not scope:
                if cls:
                    syms.methods[cls].append(child.name)
                    new_scope = f"{cls}.{child.name}"
                else:
                    syms.functions.append(child.name)
                    new_scope = child.name
            if isinstance(child, ast.Call):
                f = child.func
                if isinstance(f, ast.Name):
                    syms.calls.append(f.id)
                    syms.scoped_calls.append((scope, f.id, ""))
                elif isinstance(f, ast.Attribute):
                    recv = f.value.id if isinstance(f.value, ast.Name) else ""
                    syms.calls.append(f.attr)
                    syms.scoped_calls.append((scope, f.attr, recv))
            visit(child, cls, new_scope)

    visit(tree, "", "")
    syms.imports = _imports(source, "python")
    return syms


def extract_module(source: str, path: str) -> ModuleSymbols:
    """Extract symbols, preferring tree-sitter, falling back to stdlib ast."""
    ts = _extract_treesitter(source, path)
    if ts is not None:
        return ts
    return _extract_ast(source, path)
