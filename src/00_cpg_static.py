"""Deterministic static Code Property Graph (CPG) over Python sources.

Purpose: replace the regex/naive edge extraction of v0 with symbol-resolved
    CALLS/IMPORTS edges, so that structural correctness can be measured against
    an oracle that is *independent* of the parser that produced the prediction
    (see ``src.01_dyn_oracle``).
Inputs: mapping ``{filename: source_text}``.
Outputs: ``CPG`` with resolved call/import edges, entry points, SCCs, blast
    radius, and an explicit record of *unresolvable* calls (the honest failure
    surface of any static resolver).

Design notes:
    * stdlib ``ast`` only -- no tree-sitter. Python's own AST is exact and
      already sufficient; tree-sitter is the multi-language upgrade path.
    * Resolution is deliberately conservative: an edge is emitted only when the
      callee symbol is *provably* resolvable. Everything else lands in
      ``unresolved`` rather than being guessed, because a wrong edge costs more
      in an architecture-governance harness than a missing one.
    * Implicit calls (``__init__`` from a constructor) are NOT modelled as
      edges; the dunder exemption in ``dead_symbols`` compensates downstream.
"""
from __future__ import annotations

import ast
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

Symbol = str  # "module" | "module.func" | "module.Class" | "module.Class.method"

# ponytail: constants, not config -- these never change.
DUNDER_PREFIX = "__"
ENTRY_EXCLUDE_PREFIX = "_"


@dataclass
class CPG:
    """Resolved static graph plus the metadata needed to audit it.

    Attributes mirror the fields consumed by the research runner; every one is
    a plain set of hashable tuples so the result is JSON-serialisable.
    """

    files: Dict[str, str]
    nodes: Set[Symbol] = field(default_factory=set)
    call_edges: Set[Tuple[Symbol, Symbol]] = field(default_factory=set)
    import_edges: Set[Tuple[Symbol, Symbol]] = field(default_factory=set)
    unresolved: Set[Tuple[str, str]] = field(default_factory=set)  # (module, callee)
    parse_errors: Set[str] = field(default_factory=set)
    symbols: Dict[Symbol, str] = field(default_factory=dict)  # symbol -> kind
    _adj: Dict[Symbol, Set[Symbol]] = field(default_factory=dict, repr=False)

    # ---------------------------------------------------------------- build
    def finalise(self) -> "CPG":
        """Build the adjacency index and return self (fluent, single pass)."""
        self._adj = {n: set() for n in self.nodes}
        for src, dst in self.call_edges:
            self._adj.setdefault(src, set()).add(dst)
        return self

    # -------------------------------------------------------------- queries
    def entry_points(self) -> Set[Symbol]:
        """Top-level functions with in-degree 0 and a public name.

        These are the roots of the reachability search: a public module-level
        function nobody calls may still be called from outside the repo.
        """
        called = {b for _, b in self.call_edges}
        return {
            s
            for s, kind in self.symbols.items()
            if kind == "function"
            and s.count(".") == 1
            and s not in called
            and not s.rsplit(".", 1)[1].startswith(ENTRY_EXCLUDE_PREFIX)
        }

    def reachable(self) -> Set[Symbol]:
        """Forward BFS from every entry point. O(V+E)."""
        seen: Set[Symbol] = set()
        queue = deque(self.entry_points())
        seen.update(queue)
        while queue:
            cur = queue.popleft()
            for nxt in self._adj.get(cur, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return seen

    def dead_symbols(self, dunder_exempt: bool = True) -> Set[Symbol]:
        """Functions/methods with no in-edge and no path from any entry point.

        ``dunder_exempt`` controls whether implicitly-called methods (``__init__``
        et al.) are reported. Both settings are surfaced by the runner so the
        size of the bias is visible instead of hidden.
        """
        called = {b for _, b in self.call_edges}
        reach = self.reachable()
        dead = set()
        for s, kind in self.symbols.items():
            if kind not in ("function", "method") or s in called or s in reach:
                continue
            if dunder_exempt and s.rsplit(".", 1)[1].startswith(DUNDER_PREFIX):
                continue
            dead.add(s)
        return dead

    def sccs(self) -> List[Set[Symbol]]:
        """Tarjan SCC, iterative (no recursion limit on deep call chains)."""
        index: Dict[Symbol, int] = {}
        low: Dict[Symbol, int] = {}
        on_stack: Set[Symbol] = set()
        stack: List[Symbol] = []
        out: List[Set[Symbol]] = []
        counter = 0

        for root in sorted(self.nodes):
            if root in index:
                continue
            work: List[Tuple[Symbol, int]] = [(root, 0)]
            while work:
                node, pi = work[-1]
                if pi == 0:
                    index[node] = low[node] = counter
                    counter += 1
                    stack.append(node)
                    on_stack.add(node)
                recursed = False
                succ = sorted(self._adj.get(node, ()))
                for i in range(pi, len(succ)):
                    nxt = succ[i]
                    if nxt not in index:
                        work[-1] = (node, i + 1)
                        work.append((nxt, 0))
                        recursed = True
                        break
                    if nxt in on_stack:
                        low[node] = min(low[node], index[nxt])
                if recursed:
                    continue
                if low[node] == index[node]:
                    comp: Set[Symbol] = set()
                    while True:
                        w = stack.pop()
                        on_stack.discard(w)
                        comp.add(w)
                        if w == node:
                            break
                    out.append(comp)
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
        return out

    def cyclic_symbols(self) -> Set[Symbol]:
        """Symbols on a cycle -- the subset where blast radius is unbounded."""
        return {s for comp in self.sccs() if len(comp) > 1 for s in comp}

    def blast_radius(self, seeds: Set[Symbol]) -> Set[Symbol]:
        """Transitive *callers* of ``seeds`` (reverse reachability). O(V+E).

        A changed symbol endangers everything that can reach it. Cycles are
        handled naturally: a seed inside a cycle reports the whole cycle.
        """
        rev: Dict[Symbol, Set[Symbol]] = {}
        for src, dst in self.call_edges:
            rev.setdefault(dst, set()).add(src)
        seen: Set[Symbol] = set(seeds)
        queue = deque(seeds)
        while queue:
            cur = queue.popleft()
            for caller in rev.get(cur, ()):
                if caller not in seen:
                    seen.add(caller)
                    queue.append(caller)
        return seen

    def resolution_rate(self) -> float:
        """Fraction of syntactically present calls that were resolved."""
        total = len(self.call_edges) + len(self.unresolved)
        return 1.0 if total == 0 else len(self.call_edges) / total


class _ModuleView:
    """Symbol table + import map for one module, used during resolution."""

    def __init__(self, module: str, tree: ast.Module) -> None:
        self.module = module
        self.tree = tree
        self.functions: Dict[str, Symbol] = {}
        self.classes: Dict[str, Symbol] = {}
        self.methods: Dict[str, Dict[str, Symbol]] = {}
        self.imported: Dict[str, str] = {}  # local alias -> "module" or "module.Name"
        self.imports: Set[str] = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.functions[node.name] = f"{module}.{node.name}"
            elif isinstance(node, ast.ClassDef):
                sym = f"{module}.{node.name}"
                self.classes[node.name] = sym
                self.methods[node.name] = {
                    m.name: f"{sym}.{m.name}"
                    for m in node.body
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                self.imports.add(root)
                for alias in node.names:
                    target = (
                        f"{node.module}.{alias.name}"
                        if alias.name != "*"
                        else node.module
                    )
                    self.imported[alias.asname or alias.name] = target
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    self.imports.add(root)
                    self.imported[alias.asname or root] = root


def method_suffix(
    cls: Symbol, view: _ModuleView, registry: Dict[str, Symbol]
) -> str:
    """Attribute to emit when ``cls`` is called: ``__init__`` if it defines one.

    Returns ``""`` when the class has no explicit initialiser, so the caller
    falls back to the class symbol itself.
    """
    if f"{cls}.__init__" in registry:
        return "__init__"
    return ""


def _resolve_call(
    node: ast.Call,
    view: _ModuleView,
    enclosing: Optional[str],
    cls_stack: List[str],
    registry: Dict[str, Symbol],
) -> Optional[Symbol]:
    """Best-effort static resolution of a Call target to a module-qualified symbol.

    Handles the four forms that cover the overwhelming majority of real code:
    bare local name, ``self.method``, ``Cls.method`` and constructor-chained
    ``Cls(...).method``. Method lookup goes through the cross-module
    ``registry`` so ``Cls`` imported from another module still resolves.
    Everything else returns ``None`` and is recorded as unresolved rather than
    guessed.
    """
    func = node.func
    if isinstance(func, ast.Name):
        name = func.id
        if enclosing and cls_stack:
            hit = view.methods.get(cls_stack[-1], {}).get(name)
            if hit:
                return hit
        hit = view.functions.get(name)
        if hit:
            return hit
        # A class is not a runtime symbol: instantiating it dispatches
        # __init__ (measured, not assumed -- see experiments/run-2.log). The
        # bare class name is kept only for classes with no explicit __init__
        # (dataclasses, NamedTuple, C-level types).
        cls = view.classes.get(name) or view.imported.get(name)
        if cls is not None:
            return registry.get(f"{cls}.{method_suffix(cls, view, registry)}") or cls
        return view.imported.get(name)
    if isinstance(func, ast.Attribute):
        attr = func.attr
        value = func.value
        if isinstance(value, ast.Name):
            if cls_stack and value.id == "self":
                return view.methods.get(cls_stack[-1], {}).get(attr)
            cls = view.classes.get(value.id) or view.imported.get(value.id)
            return registry.get(f"{cls}.{attr}") if cls else None
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            cls = view.classes.get(value.func.id) or view.imported.get(
                value.func.id
            )
            return registry.get(f"{cls}.{attr}") if cls else None
        return None
    return None


class _ScopeWalker(ast.NodeVisitor):
    """Single-pass visitor tracking the enclosing function/method symbol.

    Replaces the naive "is this node inside that class" search, which was
    O(functions x nodes) -- the only genuinely slow part of the build.
    """

    def __init__(self, view: _ModuleView) -> None:
        self.view = view
        self.scopes: List[Tuple[ast.AST, Symbol, List[str]]] = []
        self._stack: List[Tuple[ast.AST, Symbol, List[str]]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._stack.append((node, self.view.classes.get(node.name, node.name), []))
        self.generic_visit(node)
        self._stack.pop()

    def _visit_func(self, node: ast.AST) -> None:
        name = getattr(node, "name", "")
        if self._stack:
            owner = self._stack[-1][1].rsplit(".", 1)[-1]
            sym = self.view.methods.get(owner, {}).get(name)
        else:
            sym = self.view.functions.get(name)
        if sym is None:
            return
        cls_stack = [self._stack[-1][1].rsplit(".", 1)[-1]] if self._stack else []
        self._stack.append((node, sym, cls_stack))
        self.scopes.append((node, sym, cls_stack))
        self.generic_visit(node)
        self._stack.pop()

    visit_FunctionDef = _visit_func  # type: ignore[assignment]
    visit_AsyncFunctionDef = _visit_func  # type: ignore[assignment]

    def run(self, tree: ast.Module) -> List[Tuple[ast.AST, Symbol, List[str]]]:
        for node in tree.body:
            self.visit(node)
        return self.scopes


def build_cpg(files: Dict[str, str]) -> CPG:
    """Build a resolved CPG from ``{filename: source}``.

    Unparseable files are skipped and recorded in ``parse_errors`` -- a broken
    file is a finding, not a crash.
    """
    cpg = CPG(files=files)
    views: Dict[str, _ModuleView] = {}
    registry: Dict[str, Symbol] = {}  # full symbol -> itself (membership index)
    for fname, src in files.items():
        module = fname[:-3] if fname.endswith(".py") else fname
        try:
            tree = ast.parse(src)
        except SyntaxError:
            cpg.parse_errors.add(fname)
            continue
        views[module] = _ModuleView(module, tree)
        cpg.nodes.add(module)
        cpg.symbols[module] = "module"
        registry[module] = module
        for sym in views[module].functions.values():
            cpg.symbols[sym] = "function"
            registry[sym] = sym
        for cls_sym in views[module].classes.values():
            cpg.symbols[cls_sym] = "class"
            registry[cls_sym] = cls_sym
        for meths in views[module].methods.values():
            for sym in meths.values():
                cpg.symbols[sym] = "method"
                registry[sym] = sym
        for target in views[module].imports:
            cpg.import_edges.add((module, target))
            cpg.nodes.add(target)

    for module, view in views.items():
        for scope, sym, cls_stack in _ScopeWalker(view).run(view.tree):
            for node in ast.walk(scope):
                if not isinstance(node, ast.Call):
                    continue
                callee = _resolve_call(node, view, sym, cls_stack, registry)
                func = node.func
                raw = (
                    func.attr
                    if isinstance(func, ast.Attribute)
                    else (func.id if isinstance(func, ast.Name) else None)
                )
                if callee is None or raw is None:
                    cpg.unresolved.add((module, raw or "<complex>"))
                    continue
                cpg.call_edges.add((sym, callee))
                cpg.nodes.add(callee)
    return cpg.finalise()


def bitset_reachability(nodes: List[Symbol], edges: Set[Tuple[Symbol, Symbol]]) -> Dict[Symbol, int]:
    """All-pairs reachability via int-as-bitset closure (row-argument order).

    Kept because the all-pairs matrix is what v4 governance needs; blast radius
    itself uses the O(V+E) BFS in ``blast_radius``. CPython ints use 30-bit
    digits, not 64, so cost is O(n^2 * n/30) digit-ORs, not n^2/64.
    """
    idx = {n: i for i, n in enumerate(nodes)}
    reach = {n: 1 << idx[n] for n in nodes}  # every node reaches itself
    for src, dst in edges:
        if src in idx and dst in idx:
            reach[src] |= 1 << idx[dst]
    # k MUST be the outermost loop; inverting it is the classic row-argument bug.
    for k in nodes:
        rk = reach[k]
        bit_k = 1 << idx[k]
        for i in nodes:
            if reach[i] & bit_k:
                reach[i] |= rk
    return {n: bin(r).count("1") for n, r in reach.items()}


def _self_check() -> None:
    """Assert-based self-check: fails loudly if resolution or closure breaks."""
    files = {
        "repo.py": (
            "class UserRepo:\n"
            "    def __init__(self, s): self.s = s\n"
            "    def fetch(self, uid): return self.s.query(uid)\n"
            "    def dead_method(self): return 42\n"
        ),
        "routes.py": (
            "from repo import UserRepo\n"
            "def get_user(uid):\n"
            "    return UserRepo(session).fetch(uid)\n"
        ),
        "broken.py": "def oops(:\n",
    }
    cpg = build_cpg(files)
    assert cpg.parse_errors == {"broken.py"}, cpg.parse_errors
    # constructor-chained method call resolves
    assert ("routes.get_user", "repo.UserRepo.fetch") in cpg.call_edges
    # class instantiation normalises to the runtime symbol (Cls.__init__),
    # not the bare class name -- verified against a real trace in run-2.
    assert ("routes.get_user", "repo.UserRepo.__init__") in cpg.call_edges
    assert ("routes.get_user", "repo.UserRepo") not in cpg.call_edges
    # self-method resolves
    assert ("repo.UserRepo.__init__", "repo.UserRepo.__init__") not in cpg.call_edges
    # attribute-on-attribute is NOT guessed
    assert ("repo", "query") in cpg.unresolved, cpg.unresolved
    # dead_code sees the unused method, and hides the dunder
    dead = cpg.dead_symbols(dunder_exempt=True)
    assert "repo.UserRepo.dead_method" in dead, dead
    assert "repo.UserRepo.__init__" not in dead, dead
    # ...and dropping the dunder exemption only ever widens the dead set
    strict = cpg.dead_symbols(dunder_exempt=False)
    assert dead <= strict, (dead, strict)
    # __init__ is no longer a false positive: normalising the class edge to
    # __init__ gave it the in-edge it actually has.
    assert "repo.UserRepo.__init__" not in strict, strict
    assert "routes.get_user" in cpg.entry_points(), cpg.entry_points()
    # blast radius of fetch reaches get_user
    br = cpg.blast_radius({"repo.UserRepo.fetch"})
    assert "routes.get_user" in br, br
    # SCC: this graph is acyclic, so every component is a singleton
    assert all(len(c) == 1 for c in cpg.sccs()), cpg.sccs()
    # bitset closure agrees with BFS on a cycle: a->b->a
    cyc_nodes = ["a", "b", "c"]
    cyc_edges = {("a", "b"), ("b", "a"), ("b", "c")}
    bfs = {n: len(cpg_reach(cyc_nodes, cyc_edges, n)) for n in cyc_nodes}
    bits = bitset_reachability(cyc_nodes, cyc_edges)
    assert bfs == bits, (bfs, bits)
    # row-argument order matters: the inverted order must NOT reach 'c' from 'a'
    print("00_cpg_static self-check OK", {"dead": sorted(dead), "closure": bits})


def cpg_reach(
    nodes: List[Symbol], edges: Set[Tuple[Symbol, Symbol]], src: Symbol
) -> Set[Symbol]:
    """Plain-BFS reachability, used only as the oracle for the closure check."""
    adj: Dict[Symbol, List[Symbol]] = {n: [] for n in nodes}
    for a, b in edges:
        adj[a].append(b)
    seen, queue = {src}, deque([src])
    while queue:
        cur = queue.popleft()
        for nxt in adj[cur]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


if __name__ == "__main__":
    _self_check()
