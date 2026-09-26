"""Independent dynamic oracle for call-graph correctness.

Purpose: provide a ground truth for "is this call edge real?" that is *not*
    produced by re-parsing the source. A second static parse shares every
    blind spot of the first (an AST-based predictor scores F1=1.0 against an
    AST-based truth while both miss the same constructor-chained calls), so it
    cannot measure structural correctness -- only self-consistency.
Inputs: mapping ``{filename: source_text}``.
Outputs: ``DynOracle`` exposing the set of dispatches actually observed at
    runtime, plus the coverage of that observation.

Method: an auto-generated harness invokes every module-level callable with
    synthetic dummy arguments while ``sys.settrace`` records real ``call``
    events as ``(caller_symbol, callee_symbol)`` pairs.

Known limitation, stated rather than hidden: the observed set is *incomplete by
construction* -- only paths the harness actually exercises appear. That biases
symmetric F1 low (see equations.md row 1 note), so precision and coverage are
reported as the primary honest numbers and F1 is secondary.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import os
import signal
import sys
import tempfile
import types
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

Symbol = str
Dispatch = Tuple[Symbol, Symbol]

CALL_BUDGET_SECONDS = 2  # ponytail: per-call alarm; unbounded user code hangs the run
MAX_HARNESS_CALLS = 64


class _Timeout(Exception):
    """Raised when a single harness invocation exceeds CALL_BUDGET_SECONDS."""


@dataclass
class DynOracle:
    """Observed runtime dispatches and what the harness failed to exercise."""

    dispatches: Set[Dispatch] = field(default_factory=set)
    invoked: Set[Symbol] = field(default_factory=set)
    import_failed: Dict[str, str] = field(default_factory=dict)
    timed_out: Set[Symbol] = field(default_factory=set)

    def covered_symbols(self) -> Set[Symbol]:
        return {b for _, b in self.dispatches} | self.invoked

    def precision(self, predicted: Set[Dispatch]) -> float:
        """Share of predicted edges that the runtime actually dispatched.

        The primary honest number. A governance harness that reports a change
        to a caller that is not really coupled is worse than one that stays
        silent, so false edges are the expensive error and this is what we hold
        the predictor to.
        """
        if not predicted:
            return 1.0
        return len(predicted & self.dispatches) / len(predicted)

    def recall(self, predicted: Set[Dispatch]) -> float:
        """Share of *observed* dispatches the predictor reproduced.

        Deliberately not F1: the observed set is incomplete by construction, so
        symmetric F1 is biased low and would conflate "predictor is wrong" with
        "harness never ran that path". Precision and recall are reported
        separately and the misses are printed, not averaged away.
        """
        if not self.dispatches:
            return 0.0
        return len(predicted & self.dispatches) / len(self.dispatches)

    def missed(self, predicted: Set[Dispatch]) -> Set[Dispatch]:
        """Observed dispatches the predictor failed to reproduce."""
        return self.dispatches - predicted

    def false_edges(self, predicted: Set[Dispatch]) -> Set[Dispatch]:
        """Predicted edges the runtime never dispatched."""
        return set(predicted) - self.dispatches

    def confirmed_dead(self, predicted_dead: Set[Symbol]) -> Set[Symbol]:
        """Predicted-dead symbols the trace proves are never dispatched."""
        reached = self.covered_symbols()
        return {s for s in predicted_dead if s not in reached}


def _dummy_args(func: Callable) -> List[Tuple[object, ...]]:
    """Candidate argument tuples for an arbitrary callable, cheapest first.

    Deduplicated by arity so we call each target at most a handful of times;
    the goal is to make the body execute, not to assert on its result.
    """
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return [()]
    required = [
        p
        for p in sig.parameters.values()
        if p.default is inspect.Parameter.empty
        and p.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if not required:
        return [()]
    out: List[Tuple[object, ...]] = []
    for filler in ((), (1,), ("x",), (1, "x"), (1, 2)):
        if len(filler) >= len(required):
            out.append(filler[: len(required)])
    return out or [(1,) * len(required)]


def _top_level_callables(module: types.ModuleType) -> List[Symbol]:
    """Qualified names of importable module-level functions (not classes)."""
    out = []
    for name, obj in vars(module).items():
        if inspect.isfunction(obj) and getattr(obj, "__module__", None) == module.__name__:
            out.append(f"{module.__name__}.{name}")
    return sorted(out)


class _Tracer:
    """Collects (caller, callee) symbol pairs from interpreter call events.

    Python 3.10 has no ``code.co_qualname``, so a frame only reveals
    ``fetch``, not ``UserRepo.fetch``. Class identity is therefore recovered
    from a code-object index built out of the repo's own modules, which keeps
    the oracle's symbol vocabulary identical to the static CPG's.
    """

    def __init__(self, index: Optional[Dict[int, str]] = None) -> None:
        self.events: Set[Dispatch] = set()
        self.index: Dict[int, str] = index or {}

    def _sym(self, frame) -> str:  # noqa: ANN001 - frame type is not importable
        module = frame.f_globals.get("__name__", "<unknown>")
        qualname = self.index.get(id(frame.f_code))
        return f"{module}.{qualname}" if qualname else f"{module}.{frame.f_code.co_name}"

    def __call__(self, frame, event, arg):  # noqa: ANN001 - CPython trace protocol
        if event == "call":
            self.events.add((self._sym(frame.f_back) if frame.f_back else "<module>", self._sym(frame)))
        return self.__call__


def _code_index(module: types.ModuleType) -> Dict[int, str]:
    """Map ``id(func.__code__)`` -> dotted qualname for one imported module.

    Walks module-level functions and class methods so trace events carry the
    same ``module.Class.method`` identity the static CPG emits.
    """
    index: Dict[int, str] = {}

    def _add(obj: object, qualname: str) -> None:
        code = getattr(obj, "__code__", None)
        if code is not None:
            index[id(code)] = qualname

    for name, obj in vars(module).items():
        if inspect.isfunction(obj):
            _add(obj, name)
        elif inspect.isclass(obj):
            for mname, meth in vars(obj).items():
                _add(meth, f"{name}.{mname}")
    return index


def _harness(module: types.ModuleType, targets: List[Symbol]) -> None:
    """Invoke every target, swallowing errors -- we want dispatches, not results."""
    for sym in targets:
        name = sym.split(".", 1)[1]
        func = getattr(module, name, None)
        if func is None:
            continue
        for args in _dummy_args(func):
            try:
                signal.setitimer(signal.ITIMER_REAL, CALL_BUDGET_SECONDS)
                func(*args)
                break  # one successful entry reveals the call graph
            except _Timeout:
                break
            except BaseException:  # noqa: BLE001 - user code may raise anything
                continue  # try the next arity
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)


def run_oracle(files: Dict[str, str]) -> DynOracle:
    """Import every module from ``files`` and trace dispatches under a harness.

    Modules are materialised in a temp directory because import needs real
    files. Import side effects are contained by the temp dir and the per-call
    alarm; this is only ever pointed at local fixtures, never at an untrusted
    downloaded repo.
    """
    oracle = DynOracle()
    local_modules = {f[:-3] for f in files if f.endswith(".py")}
    with tempfile.TemporaryDirectory(prefix="archimind_oracle_") as tmp:
        for fname, src in files.items():
            if not fname.endswith(".py"):
                continue
            try:
                ast.parse(src)
            except SyntaxError:
                oracle.import_failed[fname] = "unparseable"
                continue
            with open(os.path.join(tmp, fname), "w") as fh:
                fh.write(src)
        sys.path.insert(0, tmp)
        saved_path = sys.path[:]
        loaded: List[types.ModuleType] = []
        try:
            # Pass 1: import everything and index code objects, so the tracer can
            # recover class identity regardless of import order.
            index: Dict[int, str] = {}
            for fname in sorted(f for f in files if f.endswith(".py")):
                if fname in oracle.import_failed:
                    continue  # already rejected at the parse gate
                module_name = fname[:-3]
                try:
                    spec = importlib.util.spec_from_file_location(
                        module_name, os.path.join(tmp, fname)
                    )
                    if spec is None or spec.loader is None:
                        oracle.import_failed[fname] = "no spec"
                        continue
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = mod
                    spec.loader.exec_module(mod)
                except BaseException as exc:  # noqa: BLE001
                    oracle.import_failed[fname] = type(exc).__name__
                    continue
                loaded.append(mod)
                index.update(_code_index(mod))
            # Pass 2: trace. Targets are resolved before tracing so
            # inspect/enum frames never pollute the dispatch set.
            tracer = _Tracer(index)
            for mod in loaded:
                targets = _top_level_callables(mod)[:MAX_HARNESS_CALLS]
                oracle.invoked.update(targets)
                _traced(mod, targets, tracer, oracle)
        finally:
            sys.path[:] = saved_path
            for module_name in list(sys.modules):
                if module_name in local_modules:
                    del sys.modules[module_name]
    # Only dispatches inside the repo under test count as evidence.
    oracle.dispatches = {
        d
        for d in tracer.events
        if d[0].split(".", 1)[0] in local_modules
        and d[1].split(".", 1)[0] in local_modules
    }
    return oracle


def _traced(
    module: types.ModuleType, targets: List[Symbol], tracer: _Tracer, oracle: DynOracle
) -> None:
    """Run the harness with tracing enabled, alarm-guarded."""
    def _alarm(_signum: int, _frame) -> None:  # noqa: ANN001
        raise _Timeout()

    try:
        sys.settrace(tracer)
        threading_signal = signal.signal
        threading_signal(signal.SIGALRM, _alarm)
    except (ValueError, OSError):
        oracle.import_failed[getattr(module, "__name__", "?")] = "no-trace-signal"
        sys.settrace(None)
        return
    try:
        _harness(module, targets)
    except _Timeout:
        oracle.timed_out.add(module.__name__)
    finally:
        sys.settrace(None)
        threading_signal(signal.SIGALRM, signal.SIG_DFL)


def _self_check() -> None:
    """Assert the oracle observes the dispatch that a regex parser cannot see."""
    files = {
        "db.py": "class Session:\n    def query(self, uid):\n        return {'uid': uid}\n"
                 "session = Session()\n",
        "repo.py": "from db import session\n"
                   "class UserRepo:\n"
                   "    def __init__(self, s): self.s = s\n"
                   "    def fetch(self, uid): return self.s.query(uid)\n"
                   "    def dead_method(self): return 42\n",
        "routes.py": "from db import session\n"
                     "from repo import UserRepo\n"
                     "def get_user(uid):\n"
                     "    return UserRepo(session).fetch(uid)\n",
    }
    oracle = run_oracle(files)
    observed = {b for _, b in oracle.dispatches}
    # the constructor-chained call is real and observable
    assert "repo.UserRepo.fetch" in observed, sorted(observed)
    # ... and the truly dead method is never dispatched
    assert "repo.UserRepo.dead_method" not in observed, sorted(observed)
    assert oracle.confirmed_dead({"repo.UserRepo.dead_method"}), oracle.dispatches
    # the one edge the static CPG cannot see is an attribute-on-instance call
    assert ("repo.UserRepo.fetch", "db.Session.query") in oracle.missed(
        {("routes.get_user", "repo.UserRepo.fetch")}
    ), oracle.dispatches
    # precision/recall are real numbers and disagree, which is the point
    pred = {("routes.get_user", "repo.UserRepo.fetch")}
    assert oracle.precision(pred) == 1.0
    assert 0.0 < oracle.recall(pred) < 1.0, oracle.recall(pred)
    print(
        "01_dyn_oracle self-check OK",
        {"observed": len(oracle.dispatches), "invoked": sorted(oracle.invoked)},
    )


if __name__ == "__main__":
    _self_check()
