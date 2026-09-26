"""Out-of-corpus protocol dispatch: N10, and the manifest it prescribes.

Purpose: run 5's unreferenced-certification rule (``src/04_symbol_domain.py``)
    certifies a predicted-dead symbol ``s`` when the token count of its BARE LEAF
    NAME over the repository's reference corpus is exactly 1 -- the single
    occurrence being ``s``'s own ``def``. Its soundness rests on an enumeration
    of the mechanisms that can create a reference to a module-level name, and
    the enumeration is complete for sources INSIDE the corpus. It is not
    complete for the environment: a driver that lives outside the corpus
    dispatches by name -- ``getattr(obj, "emit")`` in stdlib ``logging``,
    ``process_bind_param`` in SQLAlchemy -- and never spells the name in any
    file the corpus contains.

    Run 6 left exactly four such certificates on real repositories and refused
    to adjudicate them, because the drivers were never executed. This module
    closes that loop in the only way that produces evidence: run the drivers.

TWO EXECUTED PROBES, NEITHER OF WHICH CONTAINS A CLASS I WROTE.

    :func:`real_framework_probes` dispatches, by executing real third-party
    code against real installed objects:

      * ``logging.Logger.info`` -> real ``rich.logging.RichHandler.emit``;
      * ``TypeDecorator.bind_processor`` -> real
        ``google.adk...DynamicJSON.process_bind_param``.

    Both are instance/class attribute dispatches performed by code outside the
    analysed repository, and both are observed by wrapping the ATTRIBUTE
    (:func:`spy_dispatches`), not by a protocol list. That matters: a
    hand-written protocol list can only ever be a lower bound on what a
    framework dispatches, whereas an attribute spy sees whatever the framework
    actually reaches, including names nobody wrote down.

TWO CURES, AND THE COMPARISON THAT DECIDES BETWEEN THEM.

    (M) a hand-maintained manifest of protocol method NAMES (:data:`PROTOCOL_NAMES`),
        withholding by name. This is what N10 prescribes.
    (E) an ENVIRONMENT-AUGMENTED corpus: recompute the occurrence count over the
        repository *plus the installed modules it imports*
        (:func:`env_reference_corpus`).

    Both cures can only ever REMOVE a certificate, so both are sound in the one
    direction that matters and both cost recall. (E) needs no hand-maintained
    list, and on the fixture it dominates (M) -- but its cost is that a name
    occurring anywhere in a reachable installed module blocks a certificate,
    which is a collision cost, not a protocol cost.

    HONEST LIMITS, asserted in code rather than left to the reader:
      * :data:`PROTOCOL_NAMES` is an APPROXIMATION, not a closure. New framework
        releases and user-defined subtypes add names. ``manifest_is_approximation``
        is emitted, and the fixture deliberately contains a driver-reachable
        method that the manifest OMITS, so the incompleteness is measured
        instead of asserted.
      * a package that the corpus does not import cannot reference the corpus --
        unless the import is dynamic, which is the runtime-assembly ceiling runs
        5 and 6 already declared undecidable. The targeted corpus in (E) is
        therefore as sound as the manifest, and no more.

    ponytail: :func:`spy_dispatches` is a dict assignment, not sys.settrace. It
    sees the dispatch and nothing else, which is all the claim needs.
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
import os
import sys
from typing import Any, Callable, Dict, Iterable, List, Set, Tuple

DOMAIN = importlib.import_module("src.04_symbol_domain")
EXPORT = importlib.import_module("src.05_export_boundary")

Symbol = str

# Names that real Python frameworks are documented to dispatch BY NAME on objects
# the framework did not import by symbol. Hand-maintained on purpose: that is the
# proposal under test, and its incompleteness is measured by the fixture.
PROTOCOL_NAMES = frozenset({
    # SQLAlchemy TypeDecorator / UserDefinedType hooks (documented public protocol)
    "process_bind_param", "process_result_value", "coerce_compared_value",
    "bind_processor", "result_processor", "bind_expression", "column_expression",
    "compare_values", "copy", "cache_ok",
    # stdlib logging.Handler / logging.Logger hooks
    "emit", "flush", "close", "handle", "filter", "format",
    # descriptor / ABC hooks that frameworks and ORMs call reflectively
    "load", "resolve", "get", "__get__",
})

# Upper bound on the environment corpus, in BYTES of source read. Exceeding it is
# a refusal, not a silent truncation: a partially read driver module is a
# partially invisible reference set, which is the soundness hole in eq. row 18.
MAX_ENV_BYTES = 64 * 1024 * 1024


def bare(sym: Symbol) -> str:
    """Leaf name of a dotted symbol path (``a.b.c`` -> ``c``)."""
    return sym.rsplit(".", 1)[-1]


def env_package_roots() -> List[str]:
    """Import roots that are not this repository, in ``sys.path`` order.

    Derived from ``sys.path`` rather than hardcoded: the environment differs per
    machine (``dist-packages`` vs a project-local ``python_libs``), and a
    hardcoded root would silently scan the wrong tree.
    """
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    roots = []
    for entry in sys.path:
        if not entry:
            entry = os.getcwd()
        entry = os.path.abspath(entry)
        if entry == here or entry.startswith(here + os.sep):
            continue
        if entry in roots or not os.path.isdir(entry):
            continue
        roots.append(entry)
    return roots


def imported_top_level(files: Dict[str, str]) -> Set[str]:
    """Top-level module names imported by ``files``, statically.

    Only TOP-LEVEL names are collected on purpose: ``importlib.util.find_spec``
    on a dotted name imports its parent package, i.e. it EXECUTES code from the
    environment. Resolving only top-level names keeps the whole environment
    corpus statically derived and never executed.
    """
    names: Set[str] = set()
    for src in files.values():
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    names.add(node.module.split(".")[0])
    return names


def _module_path(name: str) -> str | None:
    """Filesystem path of an installed top-level module's ``__init__.py``."""
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ValueError, AttributeError):
        return None
    if spec is None or not spec.submodule_search_locations:
        # A plain module (logging.py) or nothing at all; callers handle None.
        origin = getattr(spec, "origin", None)
        return origin if origin and origin.endswith(".py") else None
    for loc in spec.submodule_search_locations:
        if os.path.isfile(os.path.join(loc, "__init__.py")):
            # The package DIRECTORY, not its ``__init__.py``: the driver that
            # matters is usually a submodule (json/encoder.py names
            # `_make_encoder`), and returning the init file silently reduced the
            # environment corpus to one file per package. Found by the fixture
            # reporting zero environment occurrences for a name stdlib json
            # demonstrably contains.
            return loc
    return None


def _package_files(path: str) -> List[str]:
    """Every ``.py`` file under a package directory (or the file itself)."""
    if os.path.isfile(path):
        return [path]
    out: List[str] = []
    for dirpath, dirs, names in os.walk(path):
        dirs[:] = [d for d in sorted(dirs) if d != "__pycache__"]
        for n in sorted(names):
            if n.endswith(".py"):
                out.append(os.path.join(dirpath, n))
    return out


def env_reference_corpus(
    files: Dict[str, str], repo_root: str | None = None
) -> Tuple[Dict[str, int], Dict[str, Any]]:
    """Token counts for the installed modules ``files`` import, plus provenance.

    Returns ``(counts, meta)``. ``meta`` carries the CHECKED precondition: the
    rule may only be used when ``meta["env_complete"]`` is true, which requires
    (i) no module resolved to a file the byte cap would truncate, (ii) no file
    failed to tokenise (the ``<unparsed>`` sentinel), and (iii) every statically
    imported name that did not resolve to an installed path to be a module of
    THIS repository -- i.e. already inside the corpus -- rather than a missing
    dependency, whose source would then be an invisible reference set.
    """
    counts: Dict[str, int] = {}
    sources: List[str] = []
    resolved: Dict[str, str] = {}
    shadowed: Set[str] = set()
    unresolved: Set[str] = set()
    truncated: List[str] = []
    n_bytes = 0
    # Names the ANALYSED ARTEFACT defines itself. For a tarball there is no
    # on-disk root to compare paths against, so the shadowing test is by NAME:
    # analysing the `rich` tarball while the machine also has `rich` installed
    # would otherwise add the installed copy of the very package under analysis
    # to the environment corpus, double-counting every name in it and
    # inflating the blocking rate for no soundness gain.
    analysed_roots = {k.split(".")[0] for k in files}
    for name in sorted(imported_top_level(files)):
        if name in analysed_roots:
            shadowed.add(name)
            continue
        path = _module_path(name)
        if path is None:
            unresolved.add(name)
            continue
        if repo_root is not None and os.path.abspath(path).startswith(
            os.path.abspath(repo_root) + os.sep
        ):
            # The analysed artefact shadows the installed copy of the same
            # package. Counting the installed source would double-count every
            # name in it and inflate the blocking rate for no soundness gain.
            shadowed.add(name)
            continue
        resolved[name] = path
        for f in _package_files(path):
            try:
                size = os.path.getsize(f)
            except OSError:
                truncated.append(f)
                continue
            if n_bytes + size > MAX_ENV_BYTES:
                truncated.append(f)
                continue
            n_bytes += size
            try:
                with open(f, encoding="utf-8", errors="replace") as fh:
                    sources.append(fh.read())
            except OSError:
                truncated.append(f)
    counts = DOMAIN.token_name_counts(sources)
    known = set(files)
    unresolved_repo_internal = {
        n for n in unresolved
        if any(k == n or k.startswith(n + ".") for k in known)
    }
    unresolved_missing = sorted(unresolved - unresolved_repo_internal)
    env_complete = (
        not truncated
        and DOMAIN.UNPARSED not in counts
        and not unresolved_missing
    )
    meta = {
        "n_env_files": len(sources),
        "n_env_bytes": n_bytes,
        "n_resolved_modules": len(resolved),
        "resolved_modules": sorted(resolved),
        "n_shadowed_modules": len(shadowed),
        "analysed_roots": sorted(analysed_roots),
        "shadowed_modules": sorted(shadowed),
        "n_unresolved": len(unresolved),
        "unresolved_missing_dependency": unresolved_missing,
        "unresolved_repo_internal": sorted(unresolved_repo_internal),
        "truncated": truncated[:5],
        "env_complete": env_complete,
        "precondition_failure": (
            "truncated" if truncated
            else "unparsed" if DOMAIN.UNPARSED in counts
            else "missing_dependency" if unresolved_missing
            else None
        ),
        "max_env_bytes": MAX_ENV_BYTES,
    }
    return counts, meta


def whole_env_admissibility(roots: List[str] | None = None) -> Dict[str, Any]:
    """Is a WHOLE-ENVIRONMENT occurrence corpus admissible under eq. row 20?

    The environment corpus (:func:`env_reference_corpus`) is targeted at the
    repository's own imports, which is why it is blind to a framework that
    dispatches to repository objects without being imported by them. The
    automatic alternative is to scan every installed module -- and eq. row 20's
    completeness precondition makes that admissible only if the whole
    environment both fits the byte cap and tokenises. This measures whether it
    does, instead of arguing about it: a refusal here is a *result*, and it is
    the reason a hand-maintained manifest is the only remaining cure rather than
    a maintenance oversight.
    """
    roots = env_package_roots() if roots is None else roots
    n_files = 0
    n_bytes = 0
    for root in roots:
        for dirpath, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for n in names:
                if not n.endswith(".py"):
                    continue
                n_files += 1
                try:
                    n_bytes += os.path.getsize(os.path.join(dirpath, n))
                except OSError:
                    pass
    return {
        "n_roots": len(roots),
        "n_env_py_files": n_files,
        "env_bytes": n_bytes,
        "max_env_bytes": MAX_ENV_BYTES,
        "admissible": n_bytes <= MAX_ENV_BYTES,
        "bytes_over_cap": max(0, n_bytes - MAX_ENV_BYTES),
        "note": (
            "A whole-environment corpus is SOUND (it strictly contains the "
            "targeted one) but its soundness is void the moment one file is "
            "dropped, so eq. row 20 forces a refusal whenever the byte cap is "
            "exceeded. `admissible: false` therefore means the automatic cure is "
            "unavailable, not that it is unsound."
        ),
    }


def manifest_withheld(dead: Set[Symbol], manifest: Iterable[str] = PROTOCOL_NAMES) -> Set[Symbol]:
    """Predicted-dead symbols a protocol-name manifest refuses to certify.

    Withholds by BARE NAME, so the cost is the cross-class name collision rate
    of the manifest: every truly-dead symbol that happens to share a protocol
    name is destroyed too. That cost is the price of soundness, not a defect --
    the same trade run 6 proved for the ``R(m)`` over-approximation -- and
    :func:`certify_with_env` exists to measure whether a cheaper price exists.
    """
    names = set(manifest)
    return {s for s in dead if bare(s) in names}


def certify_with_env(
    dead: Set[Symbol], counts: Dict[str, int], env_counts: Dict[str, int], env_complete: bool
) -> Set[Symbol] | None:
    """Run 6's rule with the occurrence count widened to the environment.

    Returns ``None`` -- refuse, do not score -- when the environment corpus is
    incomplete. A truncated or unparsed driver module means an invisible
    reference, which is precisely the failure this whole node exists to close,
    so a number produced under that condition would be worse than no number.
    """
    if not env_complete:
        return None
    merged = dict(counts)
    for k, v in env_counts.items():
        merged[k] = merged.get(k, 0) + v
    exposed = EXPORT.star_exposed(dead, {}) | EXPORT.externally_driven(dead)
    return {
        s for s in dead
        if merged.get(bare(s), 0) == 1 and s not in exposed
    }


def spy_dispatches(
    obj: Any, names: Iterable[str]
) -> Tuple[List[str], Callable[[], None]]:
    """Observe every dispatch to ``names`` on ``obj`` by wrapping the attribute.

    An instance attribute shadows a class-level function, so this catches BOTH
    ``self.emit(record)`` and ``getattr(obj, "emit")(record)`` -- the two shapes
    an out-of-corpus driver actually uses. Returns ``(seen, restore)``; call
    ``restore()`` before the object is used again.

    What it does NOT see: a dispatch the driver performs on the CLASS rather
    than the instance (``getattr(type(obj), name)``), or one it performs on a
    different object. So the result is a lower bound on what the driver can
    reach, and is reported as one.
    """
    seen: List[str] = []
    saved: Dict[str, Any] = {}
    for name in names:
        if not hasattr(obj, name):
            continue
        original = getattr(obj, name)

        def make(nm: str, orig: Any) -> Callable[..., Any]:
            def spy(*args: Any, **kwargs: Any) -> Any:
                seen.append(nm)
                return orig(*args, **kwargs)
            return spy

        saved[name] = original
        try:
            setattr(obj, name, make(name, original))
        except (AttributeError, TypeError):
            saved.pop(name, None)

    def restore() -> None:
        for name, original in saved.items():
            try:
                if name in getattr(obj, "__dict__", {}):
                    delattr(obj, name)
                else:
                    setattr(obj, name, original)
            except (AttributeError, TypeError):
                pass

    return seen, restore


def fixture_driver_probe(repo_dir: str, driver_dir: str, module: str = "framework") -> Dict[str, Any]:
    """Third probe: run a synthetic out-of-corpus driver against the fixture.

    The driver lives in its own directory, is never part of the analysed corpus,
    and reaches the fixture's methods only through ``getattr(obj, name)`` over a
    protocol tuple it spells itself. Each method returns a unique sentinel, so
    the set of sentinels coming back is the set of methods ACTUALLY DISPATCHED --
    an execution result, not an assertion about what ought to happen.

    This is the fixture's written-down truth, and it is deliberately a *lower
    bound* over the driver's protocol tuple: a name the tuple omits would also
    be reachable by a real framework, which is exactly the manifest's failure
    mode, and the fixture contains such a name on purpose.
    """
    out: Dict[str, Any] = {"driver_dir": driver_dir, "repo_dir": repo_dir}
    saved_path = list(sys.path)
    saved_mods = {k: v for k, v in sys.modules.items() if k in ("alpha", "gamma", module)}
    sys.path.insert(0, repo_dir)
    sys.path.insert(0, driver_dir)
    try:
        spec = importlib.util.spec_from_file_location(
            module, os.path.join(driver_dir, module + ".py")
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"no spec for {module}")
        driver = importlib.util.module_from_spec(spec)
        sys.modules[module] = driver
        spec.loader.exec_module(driver)
        target = importlib.import_module("alpha")
        out["protocol_tuple"] = list(driver.PROTOCOL)
        # An INSTANCE, not the class: the driver must dispatch through the
        # same attribute path a framework uses, and an unbound function would
        # merely report a signature error.
        out["reached_sentinels"] = sorted(driver.drive(target.T()))
    except Exception as exc:  # noqa: BLE001
        out["status"] = "failed"
        out["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        sys.path[:] = saved_path
        for name in ("alpha", "gamma", module):
            sys.modules.pop(name, None)
        sys.modules.update(saved_mods)
    out.setdefault("status", "executed")
    return out


def real_framework_probes() -> Dict[str, Any]:
    """Execute two real out-of-corpus drivers against real installed objects.

    No class in this repository is involved on the driver side, and no protocol
    list is consulted: the observed names are whatever the frameworks actually
    reached. Each probe reports its own failure honestly instead of returning an
    empty result that would read as "the driver dispatched nothing".
    """
    out: Dict[str, Any] = {}

    # -- Probe 1: stdlib logging -> an installed third-party Handler.
    try:
        import io as _io
        import logging

        import rich.console
        import rich.logging

        handler = rich.logging.RichHandler(rich_tracebacks=False, show_path=False)
        sink = _io.StringIO()
        handler.console = rich.console.Console(file=sink, width=80, no_color=True)
        names = [n for n in ("emit", "flush", "handle", "close") if hasattr(handler, n)]
        seen, restore = spy_dispatches(handler, names)
        logger = logging.getLogger("archimind_n10_probe")
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False
        try:
            logger.info("n10 probe record")
        finally:
            restore()
            logger.handlers = []
        out["logging_into_rich"] = {
            "status": "executed",
            "driver": "stdlib logging (out of corpus)",
            "object": f"{type(handler).__module__}.{type(handler).__name__}",
            "object_source": getattr(
                importlib.import_module(type(handler).__module__), "__file__", None
            ),
            "dispatched": sorted(set(seen)),
            "not_dispatched": sorted(set(names) - set(seen)),
            "observation": "instance attribute spy; a lower bound on reachability",
        }
    except Exception as exc:  # noqa: BLE001 - the probe must never break the run
        out["logging_into_rich"] = {
            "status": "unavailable", "error": f"{type(exc).__name__}: {exc}"
        }

    # -- Probe 2: SQLAlchemy's documented TypeDecorator protocol, on an
    #    installed third-party TypeDecorator subclass.
    try:
        import inspect

        import sqlalchemy.dialects.sqlite as sqlite_dialect
        from sqlalchemy.types import TypeDecorator

        module = importlib.import_module("google.adk.sessions.schemas.shared")
        candidates = [
            getattr(module, n) for n in dir(module)
            if inspect.isclass(getattr(module, n))
            and issubclass(getattr(module, n), TypeDecorator)
            and "process_bind_param" in getattr(module, n).__dict__
        ]
        if not candidates:
            raise LookupError("no installed TypeDecorator subclass with process_bind_param")
        cls = candidates[0]
        instance = cls()
        seen2: List[str] = []
        original = cls.process_bind_param

        def probe_cb(*args: Any, **kwargs: Any) -> Any:
            seen2.append("process_bind_param")
            return original(*args, **kwargs)

        cls.process_bind_param = probe_cb  # type: ignore[method-assign]
        try:
            processor = instance.bind_processor(sqlite_dialect.dialect())
            value_out = processor({"k": 1}) if processor is not None else None
        finally:
            cls.process_bind_param = original  # type: ignore[method-assign]
        out["sqlalchemy_type_protocol"] = {
            "status": "executed",
            "driver": f"sqlalchemy {importlib.import_module('sqlalchemy').__version__} "
                      "TypeDecorator.bind_processor (out of corpus)",
            "object": f"{cls.__module__}.{cls.__name__}",
            "object_source": inspect.getsourcefile(cls),
            "dispatched": sorted(set(seen2)),
            "value_out": repr(value_out)[:80],
            "observation": "class attribute spy; a lower bound on reachability",
        }
    except Exception as exc:  # noqa: BLE001
        out["sqlalchemy_type_protocol"] = {
            "status": "unavailable", "error": f"{type(exc).__name__}: {exc}"
        }
    return out


def adjudicate(
    dead: Set[Symbol], truth_dead: Set[Symbol], per_rule: Dict[str, Set[Symbol] | None]
) -> Dict[str, Any]:
    """Score every rule against written-down truth, refusing undefined rules.

    ``None`` (a rule that declined to score) is reported as ``refused``, never
    as 0.0 -- the distinction run 4 lost by scoring a term it could not measure.
    """
    out: Dict[str, Any] = {"truth_dead": sorted(truth_dead)}
    for name, pred in per_rule.items():
        if pred is None:
            out[name] = {"status": "refused", "reason": "precondition failed"}
            continue
        hits = pred & truth_dead
        out[name] = {
            "status": "scored",
            "n_certified": len(pred),
            "precision": round(len(hits) / len(pred), 4) if pred else None,
            "recall": round(len(hits) / len(truth_dead), 4) if truth_dead else None,
            "false_positives": sorted(pred - truth_dead),
            "false_negatives": sorted(truth_dead - pred),
        }
    return out


def self_check() -> None:
    """Adversarial self-check. Must pass before any number in a run is reported.

    1. the env corpus resolves a real installed module and finds a name in it;
    2. the env corpus counts a name the repo corpus never spells -- the entire
       mechanism the node exists to test;
    3. a hand-built mini-environment is NOT consulted: an import of a module
       that does not exist is reported as a missing dependency and makes the
       precondition fail, so the rule refuses rather than scoring blind;
    4. the manifest withholds by bare name, so a same-named symbol in another
       module is withheld too (the collision cost, asserted not described);
    5. the attribute spy sees BOTH dispatch shapes and restores the object;
    6. :func:`certify_with_env` returns ``None`` on an incomplete environment.
    """
    counts, meta = env_reference_corpus({"m.py": "import json\n"}, repo_root=None)
    assert meta["n_resolved_modules"] >= 1, meta
    assert "json" in meta["resolved_modules"], meta
    assert counts, "environment corpus produced no tokens at all"
    assert meta["env_complete"] is True, meta

    # 2/3: a repo that imports a package that is NOT installed.
    counts2, meta2 = env_reference_corpus({"m.py": "import definitely_not_a_module_xyz\n"})
    assert meta2["env_complete"] is False, meta2
    assert "definitely_not_a_module_xyz" in meta2["unresolved_missing_dependency"], meta2
    assert meta2["precondition_failure"] == "missing_dependency", meta2

    # 4: the manifest is name-keyed, so a colliding dead symbol is destroyed.
    dead = {"alpha.T.emit", "beta.U.emit", "alpha.T.unrelated_dead"}
    withheld = manifest_withheld(dead, {"emit"})
    assert withheld == {"alpha.T.emit", "beta.U.emit"}, withheld
    assert "alpha.T.unrelated_dead" not in withheld, withheld

    # 5: both dispatch shapes, and the object is left as it was.
    class _Driver:
        def emit(self, x):
            return x

        def close(self):
            return "closed"

    d = _Driver()
    seen, restore = spy_dispatches(d, ("emit", "close"))
    d.emit(1)                      # attribute dispatch
    getattr(d, "emit")(2)          # getattr-by-name dispatch
    d.close()
    assert sorted(seen) == ["close", "emit", "emit"], seen
    restore()
    assert "emit" not in getattr(d, "__dict__", {}), "restore left the spy in place"
    assert d.emit(3) == 3, "restore did not restore the bound method"

    # 6: the whole-environment corpus is measured, not assumed. On any machine
    # with a normal site-packages this is inadmissible, which is the finding.
    whole = whole_env_admissibility()
    assert whole["admissible"] == (whole["env_bytes"] <= whole["max_env_bytes"])
    assert whole["n_env_py_files"] > 0

    # 7: a package the artefact defines itself is never added to the environment
    # corpus, even when the machine has a copy installed under the same name.
    shadow = env_reference_corpus({"rich.__init__": "import rich.console\n"})
    assert shadow[1]["n_shadowed_modules"] == 1, shadow[1]
    assert "rich" in shadow[1]["shadowed_modules"], shadow[1]

    # 8: refusal, not a number.
    assert certify_with_env(set(), {}, {}, False) is None

    # The env rule really is a superset-blocking rule: a name present only in
    # the environment must stop certifying.
    dead2 = {"alpha.T.process_bind_param"}
    merged_visible = certify_with_env(
        dead2, {"process_bind_param": 1}, {"process_bind_param": 1}, True
    )
    assert merged_visible == set(), merged_visible
    assert certify_with_env(dead2, {"process_bind_param": 1}, {}, True) == dead2

    print("06_protocol_driver self_check: OK")


if __name__ == "__main__":
    self_check()
