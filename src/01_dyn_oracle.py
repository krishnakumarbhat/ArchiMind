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
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

Symbol = str
Dispatch = Tuple[Symbol, Symbol]

CALL_BUDGET_SECONDS = 2  # ponytail: per-call alarm; unbounded user code hangs the run
MAX_HARNESS_CALLS = 64
#: Default event ceiling when the caller asks for a deterministic bound. Chosen
#: above anything the loop's own fixtures need, so on a terminating program the
#: ceiling does not bind and the trace is a function of the input alone.
DEFAULT_EVENT_BUDGET = 200_000


class _Timeout(Exception):
    """Raised when a single harness invocation exceeds CALL_BUDGET_SECONDS."""


class _BudgetExhausted(Exception):
    """Raised from the trace function when the event ceiling is reached.

    The point of this class is that it is raised from inside ``sys.settrace``'s
    callback, so the cut is a function of the NUMBER OF EVENTS OBSERVED and not
    of the wall clock. A program that performs the same work therefore yields the
    same cut on every machine and in every process, which is the property the
    SIGALRM budget destroys (eq. row 38).
    """


#: Per-target verdicts. Only ``COMPLETE`` may contribute to the truth set: every
#: other status means the target stopped early, and a stopped target's absent
#: dispatches are unknown rather than absent.
STATUS_COMPLETE = "COMPLETE"
STATUS_TRUNCATED_TIME = "TRUNCATED_WALLCLOCK"
STATUS_TRUNCATED_EVENTS = "TRUNCATED_EVENTS"
STATUS_ERRORED = "ERRORED"
INCOMPLETE_STATUSES = frozenset(
    {STATUS_TRUNCATED_TIME, STATUS_TRUNCATED_EVENTS, STATUS_ERRORED}
)


@dataclass
class DynOracle:
    """Observed runtime dispatches and what the harness failed to exercise."""

    dispatches: Set[Dispatch] = field(default_factory=set)
    invoked: Set[Symbol] = field(default_factory=set)
    import_failed: Dict[str, str] = field(default_factory=dict)
    timed_out: Set[Symbol] = field(default_factory=set)
    per_target: Dict[Symbol, Set[Dispatch]] = field(default_factory=dict)
    #: RUN 13 (N15). Three bookkeeping sets the wall-clock budget never had, so a
    #: truncated or crashed target could be told from a finished one.
    budget_exhausted: Set[Symbol] = field(default_factory=set)
    errored: Set[Symbol] = field(default_factory=set)
    target_status: Dict[Symbol, str] = field(default_factory=dict)
    #: Events observed by the tracer, for the determinism audit.
    n_trace_events: int = 0
    #: Which bound was in force, and whether a watchdog is armed alongside it.
    bound_kind: str = "wallclock"
    #: RUN 13: if True, a wall-clock cut discards the whole trace instead of
    #: returning it. See the ``_harness`` comment for the measurement that makes
    #: this the default worth shipping.
    void_on_watchdog: bool = False
    #: Set when a voiding watchdog fired. ``dispatches`` is then empty.
    voided: bool = False

    def covered_symbols(
        self,
        dispatches: Optional[Set[Dispatch]] = None,
        targets: Optional[List[Symbol]] = None,
    ) -> Set[Symbol]:
        """Symbols exercised by ``dispatches`` (default: everything observed).

        Both arguments are parameters so a held-out fold can report its OWN
        coverage. Using the global sets here would silently credit a caller that
        only ran in the *other* fold, which is exactly the leak a held-out
        protocol exists to catch.
        """
        seen = self.dispatches if dispatches is None else dispatches
        inv = self.invoked if targets is None else targets
        return {b for _, b in seen} | set(inv)

    def fold_targets(self, folds: int = 2) -> List[List[Symbol]]:
        """Deterministic interleaved split of the invoked targets into ``folds``.

        Interleaving on the sorted target list is the laziest split that still
        balances fold size; the point is only that the two folds share no
        harness target, so a rule learned on one is scored on genuinely
        unexercised entry points in the other.
        """
        targets = sorted(self.invoked)
        return [targets[i::folds] for i in range(folds)]

    def dispatches_for(self, targets: List[Symbol]) -> Set[Dispatch]:
        """Union of the dispatches attributed to each of ``targets``."""
        out: Set[Dispatch] = set()
        for t in targets:
            out |= self.per_target.get(t, set())
        return out

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

    def _invented_anything(self) -> bool:
        """Whether this trace could contain a dispatch that did not happen.

        L1b's asymmetry -- a partial trace hides dispatches and never invents
        them -- is CONDITIONAL on the trace being omission-only. A trace is
        omission-only by construction here (events are recorded when CPython
        reports a call), so this is False for every oracle this module builds;
        the method exists so the claim is CHECKED rather than assumed, and it is
        the seam through which a future event-synthesis or replay-based oracle
        would have to declare itself.
        """
        return False

    def completeness(self) -> Dict[str, Any]:
        """Whether this trace may be used as TRUTH, stated as a verdict.

        Run 12 added this because the loop spent ten runs drawing conclusions
        from a trace that could silently lose half its events. Run 13 splits it
        three ways, because a target that hit the wall clock, a target that hit
        the event ceiling and a target that raised are three different facts and
        only the first two are recoverable by raising a bound. A target that
        RAISED is not recoverable at all: its body may have had calls after the
        raise site, so its event set is a prefix of its call graph no matter how
        generous the bound.

        ``status`` is ``COMPLETE`` when no target was cut, ``PARTIAL`` when at
        least one was, and ``EMPTY`` when nothing was observed at all. Only
        ``COMPLETE`` supports a claim that a symbol is dead.
        """
        census: Dict[str, int] = {STATUS_COMPLETE: 0}
        for st in (STATUS_TRUNCATED_TIME, STATUS_TRUNCATED_EVENTS, STATUS_ERRORED):
            census[st] = 0
        for st in self.target_status.values():
            census[st] = census.get(st, 0) + 1
        n_targets = len(self.target_status) or len(self.per_target)
        n_incomplete = sum(census[st] for st in INCOMPLETE_STATUSES)
        if self.voided:
            status = "VOID_WATCHDOG_FIRED"
        elif not self.dispatches:
            status = "EMPTY"
        elif n_incomplete:
            status = "PARTIAL"
        else:
            status = "COMPLETE"
        return {
            "status": status,
            "voided": self.voided,
            "void_on_watchdog": self.void_on_watchdog,
            "n_targets": n_targets,
            "n_targets_complete": census[STATUS_COMPLETE],
            "n_targets_cut_by_alarm": census[STATUS_TRUNCATED_TIME],
            "n_targets_cut_by_events": census[STATUS_TRUNCATED_EVENTS],
            "n_targets_errored": census[STATUS_ERRORED],
            "status_census": census,
            "timed_out_targets": sorted(self.timed_out),
            "errored_targets": sorted(self.errored),
            "budget_exhausted_targets": sorted(self.budget_exhausted),
            "truth_coverage": (
                census[STATUS_COMPLETE] / n_targets if n_targets else 0.0
            ),
            "n_dispatches": len(self.dispatches),
            "n_trace_events": self.n_trace_events,
            "call_budget_seconds": CALL_BUDGET_SECONDS,
            "bound_kind": self.bound_kind,
            "supports_dead_claim": status == "COMPLETE",
            # L1b: incompleteness can HIDE a live symbol but never INVENT one.
            # A liveness refutation ("this edge is real, so certifying its target
            # dead is a false positive") rests on a POSITIVE observation, which a
            # partial trace still makes. So a PARTIAL trace invalidates every dead
            # claim and no liveness claim -- the asymmetry is why run 12's
            # refutation of eq. row 18 survives a trace this run calls unusable.
            "supports_liveness_claim": (
                len(self.dispatches) > 0 and not self._invented_anything()
            ),
            "note": (
                "PARTIAL means the trace lost targets to a bound. Its ABSENT "
                "dispatches are not evidence of anything, so no 'this symbol is "
                "dead' claim may be drawn from it. truth_coverage is the share "
                "of targets that finished, and it is the number to gate on."
            ),
        }


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

    def __init__(
        self,
        index: Optional[Dict[int, str]] = None,
        event_budget: Optional[int] = None,
        count_events: str = "call",
    ) -> None:
        self.events: Set[Dispatch] = set()
        self.index: Dict[int, str] = index or {}
        self.event_budget = event_budget
        #: ``"call"`` counts call events, ``"all"`` counts call AND line events.
        #: RUN 13 measured the difference: an infinite loop that makes no calls
        #: never increments a call counter, so a call budget does not bound it
        #: and the wall clock remains the only thing that stops it -- which is
        #: exactly the non-determinism the budget was introduced to remove. Line
        #: events grow with WORK, so ``"all"`` is the count that actually
        #: dominates the clock.
        if count_events not in ("call", "all"):
            raise ValueError(f"count_events must be 'call' or 'all', got {count_events!r}")
        self.count_events = count_events
        self.n_events = 0

    def _sym(self, frame) -> str:  # noqa: ANN001 - frame type is not importable
        module = frame.f_globals.get("__name__", "<unknown>")
        qualname = self.index.get(id(frame.f_code))
        return f"{module}.{qualname}" if qualname else f"{module}.{frame.f_code.co_name}"

    def __call__(self, frame, event, arg):  # noqa: ANN001 - CPython trace protocol
        # RUN 13: the budget is checked HERE, inside the trace callback, because
        # that is the only place where "how much work has been done" is a counter
        # rather than a clock reading.
        if self.count_events == "all":
            self.n_events += 1
            if self.event_budget is not None and self.n_events > self.event_budget:
                raise _BudgetExhausted()
        if event == "call":
            if self.count_events == "call":
                self.n_events += 1
                if self.event_budget is not None and self.n_events > self.event_budget:
                    raise _BudgetExhausted()
            caller = self._sym(frame.f_back) if frame.f_back else "<module>"
            self.events.add((caller, self._sym(frame)))
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


def _harness(
    module: types.ModuleType,
    targets: List[Symbol],
    tracer: "_Tracer",
    oracle: DynOracle,
    arm_watchdog: bool = True,
) -> None:
    """Invoke every target, swallowing errors -- we want dispatches, not results.

    Events are attributed *per target*: the tracer is reset before each
    invocation. Without this split the dispatch set is a single blob and a
    held-out evaluation is impossible -- a rule trained on one half of the
    targets would still be scored against dispatches produced by the other.

    RUN 13: every target now gets a written status. The event counter resets with
    the event set, so the ceiling is *per target*, which is the same granularity
    the wall-clock alarm had.
    """
    oracle.n_trace_events = 0
    for sym in targets:
        name = sym.split(".", 1)[1]
        func = getattr(module, name, None)
        if func is None:
            continue
        # RUN 13 DEFECT #1, found by measurement rather than by reading. Raising
        # from a trace function leaves CPython with tracing OFF, so after a
        # `_BudgetExhausted` cut every subsequent target recorded zero events and
        # the trace silently lost 6 of its 10 dispatches -- deterministically, on
        # every run, with a COMPLETE-looking census for the targets already
        # passed. The event bound did not merely fail to help; it destroyed more
        # truth than the wall clock did, in a way that looks like a clean run.
        #
        # RUN 13 DEFECT #2, found by the fix for #1. The counter MUST be reset
        # BEFORE the re-arm, because `sys.settrace(tracer)` is itself a call from
        # a traced frame: it emits a `call` event, the counter was still over the
        # ceiling from the previous target, so the re-arm raised immediately,
        # outside every `try`, escaped `_harness` and was caught by `_traced` --
        # which aborted the remaining targets. The first fix turned a silent loss
        # into a loud one; only the second made it correct. Both are recorded
        # because a fix that is itself instrumented needs its own test.
        tracer.n_events = 0
        sys.settrace(tracer)
        for args in _dummy_args(func):
            tracer.events = set()
            tracer.n_events = 0
            status = STATUS_COMPLETE
            try:
                if arm_watchdog:
                    signal.setitimer(signal.ITIMER_REAL, CALL_BUDGET_SECONDS)
                func(*args)
                break  # one successful entry reveals the call graph
            except _Timeout:
                # RUN 12 DEFECT, and it was in the instrument the whole loop has
                # been adjudicating against. The 2 s budget can expire mid-target,
                # and the events collected so far are PARTIAL. Before this run the
                # partial set was stored in per_target like any other and flowed
                # into oracle.dispatches, so a truncated trace was indistinguishable
                # from a complete one. Measured on synthetic_escape_repo: 6 of 7
                # runs in separate processes recorded 6 dispatches and 1 recorded
                # 12, and `Dyn.load` appeared as a callee in 1 of 7 runs. Nothing warned.
                # `timed_out` already existed as a field and was only ever written
                # by the module-level handler in _traced, which cannot fire because
                # _harness swallows the per-call _Timeout -- so the guard was dead
                # code wearing a field's name.
                oracle.timed_out.add(sym)
                status = STATUS_TRUNCATED_TIME
                if oracle.void_on_watchdog:
                    # RUN 13: a watchdog that fires VOIDS the trace. Measured
                    # reason: an event budget and a wall clock RACE, and which
                    # one binds is a property of (budget, machine load), not of
                    # the program. Under the incumbent configuration the clock
                    # won every time even with a 20M ceiling, because line-event
                    # tracing only fits ~5.7M events into 2 s. So a bound that
                    # loses the race cannot be trusted to have bounded anything,
                    # and the honest response is to return NOTHING rather than a
                    # number that depends on which bound won.
                    oracle.voided = True
                break
            except _BudgetExhausted:
                # RUN 13: the deterministic cut. Recoverable by raising the
                # ceiling, which is exactly what distinguishes it from ERRORED.
                oracle.budget_exhausted.add(sym)
                status = STATUS_TRUNCATED_EVENTS
                break
            except BaseException:  # noqa: BLE001 - user code may raise anything
                # RUN 13: not recoverable. The target's body may hold calls after
                # the raise site, so no bound makes this event set whole. Recorded
                # as its own status rather than folded into "timed out" because the
                # two fail differently: one is a budget problem, the other is a
                # program that does not terminate normally under the harness.
                oracle.errored.add(sym)
                status = STATUS_ERRORED
                continue  # try the next arity
            finally:
                if arm_watchdog:
                    signal.setitimer(signal.ITIMER_REAL, 0)
        oracle.per_target[sym] = set(tracer.events)
        oracle.target_status[sym] = status
        oracle.n_trace_events += tracer.n_events


def run_oracle(
    files: Dict[str, str],
    event_budget: Optional[int] = None,
    count_events: str = "call",
    exclusive_budget: bool = False,
    void_on_watchdog: bool = False,
) -> DynOracle:
    """Import every module from ``files`` and trace dispatches under a harness.

    Modules are materialised in a temp directory because import needs real
    files. Import side effects are contained by the temp dir and the per-call
    alarm; this is only ever pointed at local fixtures, never at an untrusted
    downloaded repo.

    ``event_budget`` is RUN 13's deterministic bound. Pass an int and the
    per-target ceiling is a count of trace events, so the returned trace is a
    function of the input program rather than of the machine's load. ``None``
    keeps the historical wall-clock behaviour, which is retained as the
    MEASURED BASELINE the determinism claim is compared against -- deleting it
    would destroy the experiment. ``count_events`` selects what the counter
    counts: ``"call"`` (cheap, and blind to a loop that makes no calls) or
    ``"all"`` (call + line events, so the counter grows with work).
    """
    oracle = DynOracle()
    oracle.bound_kind = (
        ("events" if exclusive_budget else "events+watchdog")
        + f":{count_events}"
        if event_budget is not None
        else "wallclock"
    )
    oracle.void_on_watchdog = void_on_watchdog
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
            tracer = _Tracer(index, event_budget, count_events)
            for mod in loaded:
                targets = _top_level_callables(mod)[:MAX_HARNESS_CALLS]
                oracle.invoked.update(targets)
                _traced(
                    mod, targets, tracer, oracle,
                    arm_watchdog=not exclusive_budget,
                )
        finally:
            sys.path[:] = saved_path
            for module_name in list(sys.modules):
                if module_name in local_modules:
                    del sys.modules[module_name]
    # Only dispatches inside the repo under test count as evidence. Collected
    # from the per-target map, NOT from tracer.events -- the tracer holds only
    # the last target's events once the loop is done.
    #
    # RUN 12: a target that hit the per-call alarm contributes a PARTIAL event
    # set, so it is excluded outright. A smaller complete truth set is usable and
    # a larger partial one is not -- `false_edges` reads every absent dispatch as
    # "the predictor invented this edge", so a truncated trace manufactures
    # false positives in the thing it is supposed to audit. Exclusion is the
    # conservative direction and cannot be mistaken for success.
    #
    # RUN 13: the same exclusion now covers the event ceiling and the ERRORED
    # status, and it is the reason a budget is not automatically a fix -- a
    # bigger budget turns a truncation into a completion, while a crash stays a
    # crash at every budget.
    incomplete = set().union(*INCOMPLETE_STATUSES) if INCOMPLETE_STATUSES else set()
    _bad = (
        set(oracle.timed_out)
        | set(oracle.budget_exhausted)
        | set(oracle.errored)
        | {t for t, st in oracle.target_status.items() if st in incomplete}
    )
    oracle.dispatches = set() if oracle.voided else {
        d
        for sym, events in oracle.per_target.items()
        if sym not in _bad
        for d in events
        if d[0].split(".", 1)[0] in local_modules
        and d[1].split(".", 1)[0] in local_modules
    }
    for t in list(oracle.per_target):
        oracle.per_target[t] = {
            d
            for d in oracle.per_target[t]
            if d[0].split(".", 1)[0] in local_modules
            and d[1].split(".", 1)[0] in local_modules
        }
    return oracle


def _traced(
    module: types.ModuleType,
    targets: List[Symbol],
    tracer: "_Tracer",
    oracle: DynOracle,
    arm_watchdog: bool = True,
) -> None:
    """Run the harness with tracing enabled, optionally alarm-guarded.

    ``arm_watchdog=False`` is RUN 13's exclusive mode: the count bound is the
    only bound, so the trace cannot depend on machine load. The price is that a
    target invisible to the counter is unbounded, which is why the caller has to
    choose rather than get both.
    """

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
        _harness(module, targets, tracer, oracle, arm_watchdog)
    except _Timeout:
        oracle.timed_out.add(module.__name__)
        oracle.voided = True
    except _BudgetExhausted:
        # Only reachable if the ceiling is hit outside a per-target frame, which
        # the per-target loop swallows. Kept so a future refactor cannot turn the
        # cut into a crash of the whole run.
        oracle.budget_exhausted.add(module.__name__)
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
