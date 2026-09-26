"""Automated evaluation suite for ArchiMind CPG harness variations.

Usage:
    python3 scripts/run_auto_research.py --variation v0_baseline_linear --repo synthetic_bad_repo
    python3 scripts/run_auto_research.py --variation v0_baseline_linear --repo all
    python3 scripts/run_auto_research.py --list
"""
import argparse
import ast
import gc
import importlib
import io
import json
import logging
import os
import re
import resource
import sys
import tarfile
import time
import tracemalloc
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# The NN_ filename convention makes these unimportable by name (`from src.00_...`
# is a syntax error), so they are resolved through importlib once here.
CPG_MOD = importlib.import_module("src.00_cpg_static")
DYN_MOD = importlib.import_module("src.01_dyn_oracle")
PROMOTE_MOD = importlib.import_module("src.02_trace_promote")
GATE_MOD = importlib.import_module("src.03_metric_gate")
DOMAIN_MOD = importlib.import_module("src.04_symbol_domain")
EXPORT_MOD = importlib.import_module("src.05_export_boundary")
PROTO_MOD = importlib.import_module("src.06_protocol_driver")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("auto_research")

REPOS = {
    "synthetic_bad_repo": None,  # local fixture, built on demand
    "synthetic_cpg_repo": None,  # local fixture, acyclic + dynamic-oracle friendly
    "synthetic_promo_repo": None,  # local fixture, disjoint callers across folds
    "synthetic_taint_repo": None,  # local fixture, KNOWN dead-code ground truth
    "synthetic_exports_repo": None,  # local fixture, KNOWN ground truth + export surface
    "synthetic_protocol_repo": None,  # local fixture, out-of-corpus protocol driver
    "pallets/flask": "https://codeload.github.com/pallets/flask/tar.gz/refs/heads/main",
    "psf/requests": "https://codeload.github.com/psf/requests/tar.gz/refs/heads/main",
    "tiangolo/sqlmodel": "https://codeload.github.com/tiangolo/sqlmodel/tar.gz/refs/heads/main",
    "Textualize/rich": "https://codeload.github.com/Textualize/rich/tar.gz/refs/heads/main",
}

VARIATIONS = ["v0_baseline_linear", "v1_eval_optimizer", "v2_treesitter_cpg",
              "v3_trace_informed_cpg", "v3_hybrid_cpg_rag",
              "v4_governance_harness", "v5_full_agentic_system", "n7_symbol_domain",
              "n9_export_boundary", "n10_protocol_driver"]

SKIP_DIRS = {"tests", "test", "docs", "examples", "vendor", "node_modules", ".git", "__pycache__"}
SKIP_EXT = {".png", ".jpg", ".mp4", ".gif", ".ico", ".woff", ".ttf", ".bin", ".so"}
MAX_FILE_BYTES = 200_000
MAX_FILES = 400
# N7: the reference corpus may not be truncated the way the analysis set is.
# Tokenising is streaming and costs ~30k lines/sec, and a dropped file means an
# invisible reference, which would turn the unreferenced-symbol rule into a
# false-certificate machine. Bounded well above MAX_FILES so a real repo is
# covered, and `corpus_complete` refuses outright if it is ever exceeded.
MAX_CORPUS_FILES = 4000

MERMAID_BAD = re.compile(r"(---|-->.*-->|\(\(|\)\)|\{\{|\}\}|\[\[|\]\]|#|\")")


def build_synthetic_fixture(path="experiments/fixtures/synthetic_bad_repo"):
    os.makedirs(path, exist_ok=True)
    files = {
        "routes.py": (
            "from repo import UserRepo\nfrom db import session\n"
            "def get_user(uid):\n    return UserRepo(session).fetch(uid)\n"
        ),
        "repo.py": (
            "import routes\n"
            "class UserRepo:\n"
            "    def __init__(self, s): self.s = s\n"
            "    def fetch(self, uid): return self.s.query(uid)\n"
            "    def dead_method(self): return 42\n"
        ),
        "db.py": "session = object()\n",
        "broken.py": "def oops(:\n",
    }
    for name, content in files.items():
        with open(os.path.join(path, name), "w") as fh:
            fh.write(content)
    return path


def build_cpg_fixture(path="experiments/fixtures/synthetic_cpg_repo"):
    """Fixture for dynamic-oracle scoring: acyclic imports, richer call shapes.

    `synthetic_bad_repo` has a circular import (repo -> routes -> repo) which
    makes it unloadable, and therefore unusable as a dynamic oracle subject.
    This one isolates exactly the resolution cases the CPG is being judged on.
    """
    os.makedirs(path, exist_ok=True)
    files = {
        "db.py": (
            "class Session:\n"
            "    def query(self, uid):\n"
            "        return {'uid': uid}\n"
            "    def close(self):\n"
            "        return None\n"
            "session = Session()\n"
        ),
        "repo.py": (
            "from db import session\n"
            "class UserRepo:\n"
            "    def __init__(self, s):\n"
            "        self.s = s\n"
            "    def fetch(self, uid):\n"
            "        return self.s.query(uid)\n"
            "    def dead_method(self):\n"
            "        return 42\n"
            "def orphan_helper():\n"
            "    return session.close()\n"
        ),
        "routes.py": (
            "from repo import UserRepo\n"
            "from db import session\n"
            "def get_user(uid):\n"
            "    return UserRepo(session).fetch(uid)\n"
            "def get_session():\n"
            "    return session\n"
        ),
        "broken.py": "def oops(:\n",
    }
    for name, content in files.items():
        with open(os.path.join(path, name), "w") as fh:
            fh.write(content)
    return path


def build_promo_fixture(path="experiments/fixtures/synthetic_promo_repo"):
    """Fixture whose two harness folds contain DISJOINT call sites.

    Trace-informed promotion is only worth measuring if the training fold and
    the evaluation fold share no caller, otherwise a rule that memorised the
    trace is indistinguishable from one that generalised. Every entry point
    lives in its own module (`svc_a`..`svc_d`) so `fold_targets(2)` splits the
    four of them two-and-two, and the attribute-on-instance callers
    (`UserRepo.fetch`, `AuditRepo.scan`, `Cache.load`) land in different folds.

    Two further deliberate features:
      * `store.commit()` is called ONLY from `svc_d` (fold B), so its name is
        never seen in training -> it bounds the promotion coverage ceiling.
      * `Cache.stale()` is called by nobody -> a genuinely dead symbol, so
        dead-code accuracy is measured against a confirmed true positive.
    """
    os.makedirs(path, exist_ok=True)
    files = {
        "store.py": (
            "class Store:\n"
            "    def query(self, uid):\n"
            "        return {'uid': uid}\n"
            "    def close(self):\n"
            "        return None\n"
            "    def commit(self):\n"
            "        return None\n"
            "store = Store()\n"
        ),
        "users.py": (
            "from store import store\n"
            "class UserRepo:\n"
            "    def __init__(self, s):\n"
            "        self.s = s\n"
            "    def fetch(self, uid):\n"
            "        return self.s.query(uid)\n"
        ),
        "audit.py": (
            "from store import store\n"
            "class AuditRepo:\n"
            "    def __init__(self, s):\n"
            "        self.s = s\n"
            "    def scan(self, uid):\n"
            "        return self.s.query(uid)\n"
        ),
        "cache.py": (
            "from store import store\n"
            "class Cache:\n"
            "    def __init__(self, s):\n"
            "        self.s = s\n"
            "    def load(self, uid):\n"
            "        return self.s.query(uid)\n"
            "    def stale(self):\n"
            "        return None\n"
        ),
        "svc_a.py": (
            "from store import store\n"
            "from users import UserRepo\n"
            "def get_user(uid):\n"
            "    return UserRepo(store).fetch(uid)\n"
        ),
        "svc_b.py": (
            "from store import store\n"
            "from audit import AuditRepo\n"
            "def get_audit(uid):\n"
            "    return AuditRepo(store).scan(uid)\n"
        ),
        "svc_c.py": (
            "from store import store\n"
            "def close_store():\n"
            "    return store.close()\n"
        ),
        "svc_d.py": (
            "from store import store\n"
            "from cache import Cache\n"
            "def get_cached(uid):\n"
            "    c = Cache(store)\n"
            "    c.load(uid)\n"
            "    return store.commit()\n"
        ),
    }
    for name, content in files.items():
        with open(os.path.join(path, name), "w") as fh:
            fh.write(content)
    return path


def stream_tarball(url):
    req = urllib.request.Request(url, headers={"User-Agent": "archimind-research"})
    buf = io.BytesIO()
    with urllib.request.urlopen(req, timeout=60) as resp:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            buf.write(chunk)
            if buf.tell() > 60_000_000:
                raise RuntimeError("tarball exceeds 60MB cap")
    buf.seek(0)
    return buf


def build_taint_fixture(path="experiments/fixtures/synthetic_taint_repo"):
    """Fixture whose dead-code ground truth is KNOWN and whose verdict is testable.

    Every previous dead-code claim in this loop was argued from soundness
    algebra; none had a fixture where the set of truly dead symbols was written
    down and checkable. This one does, and it is built so that each clause of
    the certification rule is load-bearing:

      `_alpha_dead`        DEAD, private, name mentioned exactly once. Must be
                           certified -- this is the symbol run 4's gate refuses
                           to touch, because `dispatch` plants a `<complex>`
                           site (`reg["handler"]()`) in the same repository.
      `_beta_dead`         DEAD, private, unreferenced. Must be certified.
      `_alpha_via_string`  LIVE, reached only through `globals()["..."]`. Must
                           NOT be certified -- proves the string-literal clause.
      `_beta_live_from_test` LIVE, imported only from `tests/`. Must NOT be
                           certified -- proves the corpus must include test
                           files even though the CPG is never built over them.
                           If the corpus excluded `tests/`, this would be the
                           false positive the whole design exists to prevent.

    Ground truth dead = {alpha._alpha_dead, beta._beta_dead}. Nothing else.
    """
    os.makedirs(os.path.join(path, "tests"), exist_ok=True)
    files = {
        "alpha.py": (
            "def dispatch(reg):\n"
            "    _wire()\n"
            "    return reg['handler']()\n"
            "def _wire():\n"
            "    return globals()['_alpha_via_string']()\n"
            "def _alpha_via_string():\n"
            "    return 2\n"
            "def _alpha_dead():\n"
            "    return 1\n"
        ),
        "beta.py": (
            "def _beta_live_from_test():\n"
            "    return 4\n"
            "def _beta_dead():\n"
            "    return 3\n"
        ),
        "tests/test_beta.py": (
            "from beta import _beta_live_from_test\n"
            "def test_live():\n"
            "    assert _beta_live_from_test() == 4\n"
        ),
    }
    for name, content in files.items():
        full = os.path.join(path, name)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as fh:
            fh.write(content)
    return path


GROUND_TRUTH_DEAD = {"alpha._alpha_dead", "beta._beta_dead"}


def build_exports_fixture(path="experiments/fixtures/synthetic_exports_repo"):
    """Fixture where the CONSUMER BOUNDARY is the thing under test (N9).

    Run 5's rule certifies 2-20% of the predicted-dead set on real repos and the
    loop could not say what the other 80-98% was. This fixture makes every
    candidate explanation falsifiable at once, and it is built so that each of
    N9's three mechanisms loads exactly one clause:

      `_core_dead`               DEAD, private, unexported, occ == 1. The
                                 baseline true positive -- both rules get it.
      `_legacy_private`          DEAD, private, and the module IS star-imported,
                                 so a star import exists. A leading underscore
                                 is NOT bound by a star import, so this stays a
                                 true positive and the naive star-import
                                 hypothesis is not accidentally confirmed.
      `legacy_star_target`       LIVE, reached ONLY through `from lib.legacy
                                 import *` in `app`. This is N9's H1: the
                                 consumer never spells the name in `lib/legacy.py`.
                                 It is NOT certified -- because `app` spells it
                                 to CALL it, which is the whole lemma.
      `public_api` / `_hidden_api` LIVE and reached through `__all__` + star
                                 import. The `__all__` STRING already puts the
                                 name in the corpus, so this route was never a
                                 hole; it is the `publicly_exported` bucket.
      `exported_never_called`    Public API with no in-corpus caller at all.
                                 Un-adjudicable from inside the corpus: an
                                 outside consumer may call it. Must be
                                 `publicly_exported`, never "dead".
      `lib.extra.twin`           LIVE, called cross-module as `extra.twin()`.
                                 The leaf name occurs in `app`, not in
                                 `lib/extra.py`, so N9's per-module rule
                                 certifies it. That is H2's false positive.
      `other.other.twin`         DEAD, and shares a basename with the live one.
                                 The global rule blocks it (collision); the
                                 per-module rule gets it. The recall H2 buys.
      `twin_dead`                DEAD, private, occ == 1. Baseline true positive.

    Ground truth dead = {lib.core._core_dead, lib.legacy._legacy_private,
                        lib.extra.twin_dead, other.other.twin}. Nothing else.
    """
    os.makedirs(path, exist_ok=True)
    files = {
        "lib/__init__.py": "from .core import public_api\n",
        "lib/core.py": (
            "__all__ = [\"public_api\", \"_hidden_api\"]\n"
            "def public_api():\n    return _hidden_api()\n"
            "def _hidden_api():\n    return 1\n"
            "def _core_dead():\n    return 2\n"
        ),
        "lib/legacy.py": (
            "def legacy_star_target():\n    return 3\n"
            "def _legacy_private():\n    return 4\n"
        ),
        "lib/api.py": (
            "__all__ = [\"exported_never_called\"]\n"
            "def exported_never_called():\n    return 5\n"
        ),
        "lib/extra.py": (
            "def twin():\n    return 6\n"
            "def twin_dead():\n    return 7\n"
        ),
        "other/other.py": "def twin():\n    return 8\n",
        "app.py": (
            "from lib.core import *\n"
            "from lib.legacy import *\n"
            "from lib import extra\n"
            "def main():\n"
            "    public_api()\n"
            "    legacy_star_target()\n"
            "    return extra.twin()\n"
        ),
    }
    for name, content in files.items():
        full = os.path.join(path, name)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as fh:
            fh.write(content)
    return path


GROUND_TRUTH_DEAD_EXPORTS = {
    "lib.core._core_dead",
    "lib.legacy._legacy_private",
    "lib.extra.twin_dead",
    "other.other.twin",
}


def _fixture_dir(repo):
    if repo == "synthetic_bad_repo":
        return build_synthetic_fixture()
    if repo == "synthetic_cpg_repo":
        return build_cpg_fixture()
    if repo == "synthetic_promo_repo":
        return build_promo_fixture()
    if repo == "synthetic_taint_repo":
        return build_taint_fixture()
    if repo == "synthetic_exports_repo":
        return build_exports_fixture()
    if repo == "synthetic_protocol_repo":
        return build_protocol_fixture()
    return None


def build_protocol_fixture(
    path="experiments/fixtures/synthetic_protocol_repo",
    driver_path="experiments/fixtures/synthetic_protocol_driver",
):
    """Fixture where the OUT-OF-CORPUS DRIVER is the thing under test (N10).

    The driver is a SEPARATE DIRECTORY. That is the whole point: it is never in
    the analysed corpus, so no occurrence count over the corpus can see it, and
    it is the only thing that can dispatch to the fixture's methods. It reaches
    them by ``getattr(obj, name)`` over a protocol tuple it spells itself --
    the shape of stdlib ``logging`` calling a Handler, and of SQLAlchemy calling
    a user type.

    Every method returns a UNIQUE SENTINEL, so the set of sentinels the driver
    returns is the set of methods actually dispatched: the fixture's liveness
    truth is an EXECUTION result, not an assertion about what ought to happen.

    Clause by clause, so each rule's cost is measurable:

      ``T.process_bind_param``      LIVE, driven. In the manifest.
      ``T.process_result_value``    LIVE, driven. In the manifest.
      ``T.coerce_compared_value``   LIVE, driven. In the manifest.
      ``T.process_literal_param``   LIVE, driven. **NOT in the manifest** -- a
                                     real documented SQLAlchemy TypeDecorator
                                     hook that the hand list omits, so the
                                     manifest's incompleteness is MEASURED
                                     rather than asserted.
      ``_fixture_dead_plain``       DEAD, private, name absent from the
                                     environment corpus. The true positive
                                     every rule should keep.
      ``beta._make_iterencode``      DEAD, and its name occurs in stdlib json,
                                     which ``beta`` imports -- so the
                                     environment-augmented rule destroys a
                                     true positive. The env rule's price.
      ``beta._beta_dead_immune``    DEAD, private, and named so that NO
                                     installed module mentions it.
      ``Collider.process_bind_param`` DEAD, and its NAME collides with the
                                     manifest. This is the manifest's price: a
                                     name-keyed rule destroys a true positive.

    Ground truth dead = {alpha.fixture_dead_plain, gamma.Collider.process_bind_param}.
    """
    os.makedirs(path, exist_ok=True)
    files = {
        "alpha.py": (
            "class T:\n"
            '    def process_bind_param(self, value):\n        return "alpha.T.process_bind_param"\n'
            '    def process_result_value(self, value):\n        return "alpha.T.process_result_value"\n'
            '    def coerce_compared_value(self, value):\n        return "alpha.T.coerce_compared_value"\n'
            '    def process_literal_param(self, value):\n        return "alpha.T.process_literal_param"\n'
            "def _fixture_dead_plain():\n    return 1\n"
        ),
        "gamma.py": (
            "class Collider:\n"
            '    def process_bind_param(self, value):\n        return "gamma.Collider.process_bind_param"\n'
        ),
        # Hole B, the OTHER out-of-corpus mechanism, in the same fixture: a
        # driver the repository IMPORTS. `beta` imports json, so the
        # environment corpus contains stdlib json -- five files, ~48kB -- and
        # json/encoder.py names `_make_iterencode`. `_make_iterencode` here is
        # DEAD, so the environment rule destroys a TRUE POSITIVE: the collision
        # cost, with written-down truth. `_beta_dead_immune` is DEAD and named
        # so that no installed module mentions it, so it is the true positive
        # every rule keeps.
        "beta.py": (
            "import json\n"
            "def _make_iterencode():\n    return 1\n"
            "def _beta_dead_immune():\n    return 2\n"
        ),
    }
    for name, content in files.items():
        with open(os.path.join(path, name), "w") as fh:
            fh.write(content)
    os.makedirs(driver_path, exist_ok=True)
    # The driver. Out of corpus by construction: a different directory that
    # `load_repo_corpus` is never pointed at.
    with open(os.path.join(driver_path, "framework.py"), "w") as fh:
        fh.write(
            '"""Stand-in for a framework that dispatches to user objects by name."""\n'
            "PROTOCOL = (\n"
            '    "process_bind_param",\n'
            '    "process_result_value",\n'
            '    "coerce_compared_value",\n'
            '    "process_literal_param",\n'
            ")\n"
            "def drive(obj):\n"
            "    reached = []\n"
            "    for name in PROTOCOL:\n"
            "        fn = getattr(obj, name, None)\n"
            "        if fn is None:\n"
            "            continue\n"
            "        reached.append(fn(None))\n"
            "    return reached\n"
        )
    return path


# The CPG treats a module's PUBLIC top-level functions as entry points, so a
# predicted-dead module-level function must be private; the fixture's dead
# functions are underscore-prefixed for that reason (the same convention
# synthetic_taint_repo uses).
GROUND_TRUTH_DEAD_PROTOCOL = {
    "alpha._fixture_dead_plain",
    "beta._make_iterencode",
    "beta._beta_dead_immune",
    "gamma.Collider.process_bind_param",
}


def load_repo_corpus(repo):
    """Dotted-path file set + full reference corpus + provenance metadata.

    N7 defect 1: ``load_repo_files`` keys tarballs by BASENAME
    (``out[parts[-1]]``), so every ``__init__.py`` in the repository collapses
    into one key, two same-named modules in different packages silently
    overwrite each other, and the resulting "module" (``app``, ``config``,
    ``utils``) is a fictitious top-level namespace that happens to collide with
    real installed packages. The analysis set here is keyed by the full dotted
    path so a collision is impossible.

    N7 defect 2 (candidate, NOT the one run 4 claimed): the reference corpus is
    EVERY ``.py`` file including the directories the analysis skips, because
    the unreferenced-symbol rule is only sound if no reference is invisible.
    """
    root = _fixture_dir(repo)
    if root is not None:
        files, corpus = {}, {}
        for dirpath, _dirs, names in os.walk(root):
            for name in sorted(names):
                if not name.endswith(".py"):
                    continue
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, root)
                dotted = rel[:-3].replace(os.sep, ".")
                with open(full) as fh:
                    src = fh.read()
                corpus[dotted] = src
                if not any(p in SKIP_DIRS for p in rel.split(os.sep)):
                    files[dotted] = src
        meta = {
            "n_py_in_artefact": len(corpus),
            "n_analysis": len(files),
            "n_corpus": len(corpus),
            "basename_collisions": [],
            "max_files_cap": MAX_CORPUS_FILES,
        }
        return files, corpus, meta

    buf = stream_tarball(REPOS[repo])
    files: dict = {}
    corpus: dict = {}
    n_py_in_tarball = 0
    oversize = 0
    with tarfile.open(fileobj=buf, mode="r|gz") as tar:
        for member in tar:
            if not member.isfile() or not member.name.endswith(".py"):
                continue
            n_py_in_tarball += 1
            if member.size > MAX_FILE_BYTES:
                oversize += 1
                continue
            if len(corpus) >= MAX_CORPUS_FILES:
                continue
            parts = member.name.split("/")
            dotted = ".".join(parts[1:])[:-3] if len(parts) > 2 else parts[-1][:-3]
            fh = tar.extractfile(member)
            if fh is None:
                continue
            try:
                src = fh.read().decode("utf-8", "replace")
            except Exception:
                continue
            corpus[dotted] = src
            if not any(p in SKIP_DIRS for p in parts) and len(files) < MAX_FILES:
                files[dotted] = src
    gc.collect()
    # How many analysis files the OLD basename keying would have destroyed.
    seen: dict = {}
    for dotted in files:
        seen.setdefault(dotted.rsplit(".", 1)[-1], []).append(dotted)
    collisions = {k: sorted(v) for k, v in seen.items() if len(v) > 1}
    meta = {
        "n_py_in_artefact": n_py_in_tarball,
        "n_analysis": len(files),
        "n_corpus": len(corpus),
        "oversize_files": oversize,
        "basename_collisions": collisions,
        "n_files_dropped_by_basename_keying": len(files) - len(seen),
        "max_files_cap": MAX_CORPUS_FILES,
    }
    return files, corpus, meta


def load_repo_files(repo):
    root = _fixture_dir(repo)
    if root is not None:
        out = {}
        for dirpath, _dirs, names in os.walk(root):
            for name in sorted(names):
                if name.endswith(".py"):
                    with open(os.path.join(dirpath, name)) as fh:
                        out[name] = fh.read()
        return out
    buf = stream_tarball(REPOS[repo])
    out = {}
    with tarfile.open(fileobj=buf, mode="r|gz") as tar:
        for member in tar:
            if not member.isfile() or len(out) >= MAX_FILES:
                continue
            parts = member.name.split("/")
            if any(p in SKIP_DIRS for p in parts):
                continue
            if not parts[-1].endswith(".py") or member.size > MAX_FILE_BYTES:
                continue
            fh = tar.extractfile(member)
            if fh is None:
                continue
            try:
                out[parts[-1]] = fh.read().decode("utf-8", "replace")
            except Exception:
                continue
    gc.collect()
    return out


def ground_truth_edges(files):
    """Deterministic AST ground truth: imports + calls per file."""
    imports, calls = set(), set()
    for fname, src in files.items():
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add((fname, node.module.split(".")[0]))
            elif isinstance(node, ast.Import):
                for a in node.names:
                    imports.add((fname, a.name.split(".")[0]))
            elif isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
                if name:
                    calls.add((fname, name))
    return imports, calls


def naive_regex_edges(files):
    """Simulate v0 weakness: regex chunk matching instead of AST."""
    pat = re.compile(r"(?:import|from)\s+([a-zA-Z0-9_\.]+)")
    call = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")
    imports, calls = set(), set()
    for fname, src in files.items():
        for m in pat.finditer(src):
            imports.add((fname, m.group(1).split(".")[0]))
        for m in call.finditer(src):
            calls.add((fname, m.group(1)))
    return imports, calls


def degrade_to_coarse(edges):
    """Project symbol-space edges onto v0's vocabulary: (module, bare name).

    v0's regex cannot tell a call from a definition and has no notion of a
    caller, so it can only be scored at (module, callee-name) granularity.
    Projecting the CPG and the oracle into the same coarse space is the only
    apples-to-apples head-to-head; anything finer flatters v2 by construction.
    """
    out = set()
    for src, dst in edges:
        if "." not in src or "." not in dst:
            continue
        out.add((src.split(".")[0], dst.split(".")[-1]))
    return out


def naive_regex_calls(files):
    """v0's predicted callee set, restated in the coarse (module, name) space."""
    pat = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")
    out = set()
    for fname, src in files.items():
        module = fname[:-3] if fname.endswith(".py") else fname
        for m in pat.finditer(src):
            out.add((module, m.group(1)))
    return out


def f1(pred, truth):
    if not pred and not truth:
        return 1.0
    if not pred or not truth:
        return 0.0
    tp = len(pred & truth)
    prec = tp / len(pred)
    rec = tp / len(truth)
    return 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec)


def mermaid_validity(sample="graph TD\n    A[routes.get_user] --> B[repo.UserRepo.fetch]\n"):
    return 0.0 if MERMAID_BAD.search(sample) else 1.0


def peak_rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def classify_dead(dead, cpg, dispatches, covered):
    """Split the predicted-dead set into the three states a trace can distinguish.

    * **refuted** -- dispatched in the evaluation fold. A false "dead" verdict,
      proven.
    * **proven** -- not dispatched, AND it has a static caller that the fold
      actually exercised, so the fold's silence is informative.
    * **unexercised** -- not dispatched, but every potential caller was either
      invisible to the static resolver (the very bug being measured) or never
      invoked in this fold. The trace's silence here proves nothing.

    Collapsing the third bucket into "confirmed dead" is what made run 2's
    `dead_code_acc=0.3333` look better than it was: a half-fold oracle cannot
    distinguish dead code from unrun code, and only the first two buckets carry
    information. Returns (strict, upper, refuted, unexercised, proven).
    """
    callees = {b for _, b in dispatches}
    reverse = {}
    for a, b in cpg.call_edges:
        reverse.setdefault(b, set()).add(a)
    refuted = dead & callees
    unexercised = {
        s
        for s in dead - refuted
        if not (reverse.get(s, set()) and (reverse[s] & covered))
    }
    proven = dead - refuted - unexercised
    n = len(dead)
    strict = len(proven) / n if n else 1.0
    upper = (len(proven) + len(unexercised)) / n if n else 1.0
    return strict, upper, sorted(refuted), sorted(unexercised), sorted(proven)


def run_v3(repo):
    """Two-fold HELD-OUT evaluation of trace-informed edge promotion (v3).

    `metric_def = dynamic-oracle-heldout-v2`. The promotion rule is learned
    from fold A's dispatches ONLY; every reported number is scored against
    fold B's dispatches ONLY. Neither the promoted graph nor its score has seen
    the evaluation fold, so unlike run 2's in-sample numbers this is a real
    generalisation measurement.

    Three rows are always produced on the SAME fold so the comparison is
    paired: the unpromoted static control, MODE A, and MODE B. A single-number
    run would be unreadable -- the whole point is that A and B differ.
    """
    files = load_repo_files(repo)
    t_start = time.time()
    oracle = DYN_MOD.run_oracle(files)
    if oracle.import_failed:
        log.warning("oracle import failures: %s", oracle.import_failed)
    fold_a, fold_b = oracle.fold_targets(2)
    d_a = oracle.dispatches_for(fold_a)
    d_b = oracle.dispatches_for(fold_b)
    covered_b = oracle.covered_symbols(d_b, fold_b)
    out = {
        "variation": "v3_trace_informed_cpg", "repo": repo, "files": len(files),
        "metric_def": "dynamic-oracle-heldout-v2",
        "fold_a_targets": fold_a, "fold_b_targets": fold_b,
        "fold_a_dispatches": len(d_a), "fold_b_dispatches": len(d_b),
        "oracle_import_failed": oracle.import_failed,
    }
    if not d_a or not d_b:
        # One honest failure beats a fabricated 0.0: with an empty fold there is
        # nothing to generalise to and every recall number is undefined.
        out["status"] = "unvalidated"
        out["reason"] = "a fold observed no dispatches; protocol undefined"
        return out

    static_probe = CPG_MOD.build_cpg(files)
    rules = PROMOTE_MOD.learn_name_rules(d_a)
    edge_a = PROMOTE_MOD.promote_mode_a(static_probe, d_a)
    edge_b = PROMOTE_MOD.promote_mode_b(static_probe, rules)
    out["learned_name_rules"] = sorted(rules.items())
    out["unresolved_call_sites"] = sorted(map(list, static_probe.unresolved_calls))
    out["promotion_coverage_ceiling"] = round(
        PROMOTE_MOD.coverage_ceiling(static_probe, rules), 4
    )

    rows = {}
    for label, promoted in (
        ("static_control", set()),
        ("mode_a", edge_a),
        ("mode_b", edge_b),
    ):
        # Rebuilt from source every time: apply_promotion mutates in place, so a
        # shared instance would leak one mode's edges into the next row.
        cpg = CPG_MOD.build_cpg(files)
        static_edges = set(cpg.call_edges)
        if promoted:
            PROMOTE_MOD.apply_promotion(cpg, promoted)
        t1 = time.time()
        seeds = {b for _, b in cpg.call_edges} or set(cpg.nodes)
        blast = cpg.blast_radius(seeds)
        blast_ms = (time.time() - t1) * 1000 + 0.5
        dead = cpg.dead_symbols(dunder_exempt=True)
        prec = PROMOTE_MOD.precision_of(cpg.call_edges, d_b)
        rec = PROMOTE_MOD.recall_of(cpg.call_edges, d_b)
        d_strict, d_upper, d_ref, d_unex, d_prov = classify_dead(
            dead, cpg, d_b, covered_b
        )
        peak = peak_rss_mb()
        lat = max(0.0, 1 - blast_ms / 2000)
        ram = max(0.0, 1 - peak / 512)
        validity = mermaid_validity()
        score = 30 * validity + 30 * prec + 20 * d_strict + 10 * lat + 10 * ram
        # Candidate metric fix, reported alongside rather than substituted: the
        # standing 30-point structural term is PRECISION-ONLY and therefore
        # cannot reward a recall improvement at all. Both are emitted so the
        # decision is visible instead of being baked in.
        f1 = 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec)
        score_f1 = 30 * validity + 30 * f1 + 20 * d_strict + 10 * lat + 10 * ram
        ho = PROMOTE_MOD.heldout(cpg.call_edges, d_b, covered_b)
        # Run 4: re-score the SAME row under the corrected metric definition.
        # Both dead terms are emitted side by side -- the standing one and the
        # certified one -- so the repair is visible as a delta, not asserted.
        gate = GATE_MOD.assess(cpg, d_b, covered_b, validity, lat, ram)
        # Newly-added edges only. `promoted - cpg.call_edges` is always empty
        # because promotion was already applied -- the caller-blind split would
        # then report 0 recall for a mode that generalised perfectly.
        split = PROMOTE_MOD.split_caller_recall(
            promoted - static_edges, d_a, d_b
        )
        rows[label] = dict(
            promoted_edges=len(promoted),
            call_edges=len(cpg.call_edges),
            struct_precision_dyn=round(prec, 4),
            struct_recall_dyn=round(rec, 4),
            struct_f1_dyn=round(f1, 4),
            **ho,
            **split,
            dead_predicted=sorted(dead),
            dead_refuted=d_ref,
            dead_unexercised=d_unex,
            dead_proven=d_prov,
            dead_code_acc=round(d_strict, 4),
            dead_code_acc_upper=round(d_upper, 4),
            cpg_resolution_rate=round(cpg.resolution_rate(), 4),
            blast_symbols=len(blast),
            blast_latency_ms=round(blast_ms, 2),
            peak_ram_mb=round(peak, 2),
            harness_score=round(score, 2),
            # RETRACTED in run 4: F1 mixes in a recall term that is not a
            # sound bound against a partial oracle (equations.md row 16). Kept
            # in the log at its run-3 value so the retraction is auditable.
            harness_score_f1_RETRACTED=round(score_f1, 2),
            in_sample=False,
            **gate,
        )
    # Deployment-shaped row: what a real deployment emits, with the rule learned
    # from ALL available traces. Its precision is 1.0 BY CONSTRUCTION (every
    # promoted edge is in the trace it was learned from -- equations.md row 9
    # C4a), so it is reported for shape only and is NOT evidence of quality and
    # NOT part of the ranking. Kept because the held-out protocol is known to
    # under-measure a deployed artifact: it cannot confirm the training fold's own
    # edges, so promotion pays an unverifiable-precision tax it would not pay in
    # production.
    d_all = oracle.dispatches
    rules_all = PROMOTE_MOD.learn_name_rules(d_all)
    dep = CPG_MOD.build_cpg(files)
    dep_static = set(dep.call_edges)
    dep_promoted = PROMOTE_MOD.promote_mode_b(dep, rules_all)
    PROMOTE_MOD.apply_promotion(dep, dep_promoted)
    dep_dead = dep.dead_symbols(dunder_exempt=True)
    rows["deployed_allfolds"] = dict(
        promoted_edges=len(dep_promoted),
        call_edges=len(dep.call_edges),
        newly_promoted=sorted(map(list, dep_promoted - dep_static)),
        struct_precision_dyn=round(
            PROMOTE_MOD.precision_of(dep.call_edges, d_all), 4
        ),
        struct_recall_dyn=round(PROMOTE_MOD.recall_of(dep.call_edges, d_all), 4),
        cpg_resolution_rate=round(dep.resolution_rate(), 4),
        dead_predicted=sorted(dep_dead),
        dead_code_acc=None,
        dead_code_acc_upper=None,
        harness_score=None,
        harness_score_f1_RETRACTED=None,
        harness_score_v3=None,
        in_sample=True,
        note="precision is 1.0 by construction; shape only, not a quality claim",
    )
    out["rows"] = rows
    out["ranked_rows"] = [k for k, v in rows.items() if not v["in_sample"]]
    out["harness_score"] = rows["mode_b"]["harness_score"]
    out["metric_def_v3"] = "certified-dead-v3"
    out["max_score_v3"] = GATE_MOD.MAX_GATED_SCORE
    out["harness_score_v3"] = rows["mode_b"]["harness_score_v3"]
    out["ranking_v3"] = sorted(
        (k for k in out["ranked_rows"]),
        key=lambda k: -rows[k]["harness_score_v3"],
    )
    out["ranking_standing"] = sorted(
        (k for k in out["ranked_rows"]),
        key=lambda k: -rows[k]["harness_score"],
    )
    # The repair's whole arithmetic claim: the 20 dead points were contributing
    # EXACTLY zero, so deleting them changes no row's score and only changes
    # the scale. Verified by subtraction, not asserted.
    out["score_unchanged_by_repair"] = all(
        abs(rows[k]["harness_score"] - rows[k]["harness_score_v3"]
            - 20 * rows[k]["dead_code_acc_strict"]) < 1e-9
        for k in out["ranked_rows"]
    )
    # ...and the honest caveat that outranks the caveat: the variants are NOT
    # separable by any sound structural term on this fixture, so neither
    # ranking may be acted on.
    out["ranking_identifiable"] = all(
        rows[k]["structural_identifiable"] for k in out["ranked_rows"]
    )
    out["ranking_caveat"] = (
        "NOT identifiable: precision is a sound lower bound but conflates "
        "'wrong' with 'unjudged'. Evaluable precision is 1.0 for every row, so "
        "no sound structural term ranks these variants. The ordering below is "
        "produced entirely by edges the oracle never adjudicated."
    )
    out["token_cost_usd"] = 0.0
    out["mermaid_validity_rate"] = mermaid_validity()
    out["structural_f1_static"] = None
    out["dead_code_acc"] = rows["mode_b"]["dead_code_acc"]
    out["harness_score_f1_RETRACTED"] = rows["mode_b"][
        "harness_score_f1_RETRACTED"
    ]
    out["peak_ram_mb"] = rows["mode_b"]["peak_ram_mb"]
    out["elapsed_s"] = round(time.time() - t_start, 2)
    # The three rows share one process, so peak RSS is cumulative and the rows
    # are not perfectly independent on the RAM sub-score. Stated, not hidden:
    # the spread across rows is <0.5 pt against a 9.5 pt contribution.
    out["caveat"] = "rows share one process; peak_ram_mb is cumulative"
    return out


def run_n7(repo):
    """N7: symbol-domain hygiene + precondition-free unreferenced certification.

    Static only. The dynamic oracle stays OFF for every non-fixture repo: it
    executes code, and these are untrusted third-party tarballs. The
    certification in `src/04_symbol_domain.py` needs no execution, which is the
    only reason a real-repo dead-code measurement is possible at all here.

    Two rows on the SAME graph, so the comparison is paired:
      ``run4_gate``   equations.md row 15 -- name matching against opaque
                      unresolved sites, gated on a repo-wide precondition.
      ``unreferenced`` equations.md row 18 -- occurrence count of the leaf name
                      over the whole reference corpus, no `<complex>` clause.
    """
    files, corpus, meta = load_repo_corpus(repo)
    t0 = time.time()
    cpg = CPG_MOD.build_cpg(files)
    dead = cpg.dead_symbols(dunder_exempt=True)
    counts = DOMAIN_MOD.token_name_counts(corpus.values())
    ident = DOMAIN_MOD.recount_identifiers_only(corpus.values())
    complete = DOMAIN_MOD.corpus_complete(
        meta["n_py_in_artefact"], meta["n_corpus"], counts
    )
    opaque = GATE_MOD.opaque_names(cpg.unresolved_calls)
    pre_ok = GATE_MOD.soundness_precondition(opaque)
    run4_cert = GATE_MOD.certify_dead(dead, opaque)
    # Occurrences inside the ANALYSIS set only, so a reference the CPG could
    # never see (a test, a doc example, a vendored package) is attributable.
    counts_analysis = DOMAIN_MOD.token_name_counts(files.values())
    new_cert = DOMAIN_MOD.certify_unreferenced(dead, counts)
    blocked = DOMAIN_MOD.name_mentioned_elsewhere(dead, counts)
    str_only = DOMAIN_MOD.blocked_by_string_only(dead, counts, ident)
    peak = peak_rss_mb()

    out = {
        "variation": "n7_symbol_domain",
        "repo": repo,
        "files_analysis": len(files),
        "files_corpus": len(corpus),
        "metric_def": "unreferenced-domain-v4",
        "max_metric": GATE_MOD.MAX_GATED_SCORE,
        # -- provenance of the load, i.e. the defect being repaired
        "corpus_meta": meta,
        # -- run 4's gate, on the repaired graph
        "run4_precondition_ok": pre_ok,
        "run4_n_certified": len(run4_cert),
        "run4_certified": sorted(run4_cert)[:10],
        # -- the new gate
        "corpus_complete": complete,
        "n_predicted_dead": len(dead),
        "n_certified": len(new_cert),
        "certification_rate": round(len(new_cert) / len(dead), 4) if dead else 0.0,
        "dead_certified": sorted(new_cert)[:10],
        "n_blocked": len(blocked),
        "n_blocked_by_string_only": len(str_only),
        "dead_blocked_by_string_only": sorted(str_only)[:10],
        "n_complex_sites": sum(
            1 for _, r in cpg.unresolved_calls
            if r == GATE_MOD.COMPLEX_SENTINEL
        ),
        "cpg_resolution_rate": round(cpg.resolution_rate(), 4),
        "cpg_parse_errors": sorted(cpg.parse_errors)[:10],
        "n_parse_errors": len(cpg.parse_errors),
        "peak_ram_mb": round(peak, 2),
        "token_cost_usd": 0.0,
        "elapsed_s": round(time.time() - t0, 2),
    }
    # Both gates are binary soundness verdicts, so the comparable quantity is
    # simply whether each one is DEFINED and how much it certifies. Emitted
    # rather than folded into a score: a "0.0 because refused" and a "0.0
    # because there is nothing to certify" are different results.
    out["run4_term_v3"] = GATE_MOD.dead_term(run4_cert, pre_ok)
    out["unreferenced_term"] = 1.0 if (complete and new_cert) else 0.0
    out["unreferenced_term_refused_reason"] = (
        "corpus_incomplete" if not complete
        else "nothing_certifiable" if not new_cert
        else None
    )
    # The falsifiable comparison, stated in the only two directions that mean
    # something. `new >= run4` would be the wrong test: run 4's UNGATED filter is
    # unsound, so a superset would be a superset of false positives.
    out["new_subset_of_run4_ungated"] = new_cert <= run4_cert
    # The decisive real-repo test of run 4's gate: it is DEFINED on the analysis
    # set, so any certified symbol whose name is additionally referenced OUTSIDE
    # that set is a demonstrated false positive -- not a suspected one. Split by
    # whether the extra mention is an identifier (a real out-of-scope caller) or
    # only a string literal (the getattr/globals escape).
    out_of_scope = {
        s for s in run4_cert
        if counts.get(DOMAIN_MOD.bare(s), 0) > counts_analysis.get(DOMAIN_MOD.bare(s), 0)
    }
    out["n_run4_cert_out_of_scope_refs"] = len(out_of_scope)
    out["run4_cert_out_of_scope_sample"] = sorted(out_of_scope)[:10]
    out["n_run4_cert_blocked_only_by_string"] = len(
        {s for s in out_of_scope if ident.get(DOMAIN_MOD.bare(s), 0)
            == counts_analysis.get(DOMAIN_MOD.bare(s), 0)}
    )
    out["n_run4_ungated_false_positives"] = len(run4_cert - new_cert) if complete else None
    # Run 4 WITH its own precondition gate applied -- the only run-4 output that
    # is defensible. Empty whenever the precondition fails.
    run4_gated = run4_cert if pre_ok else set()
    out["n_run4_gated_certified"] = len(run4_gated)
    out["n_certified_only_by_new_rule"] = len(new_cert - run4_gated)
    if repo.startswith("synthetic_"):
        # Local fixture: trusted code, so the dynamic oracle may run. Real
        # tarballs NEVER get here -- they execute third-party code, and the
        # whole point of the unreferenced rule is that it needs no execution.
        # The oracle writes each source to a tmpdir under its key and derives the
        # module name by stripping ".py", so it REQUIRES .py-suffixed keys.
        # run_n7 keys by dotted path WITHOUT the extension, and feeding it those
        # keys directly made it observe zero modules and report a suspiciously
        # round precision of 0.0 -- a silently empty measurement, not a score.
        oracle = DYN_MOD.run_oracle({f"{k}.py": v for k, v in files.items()})
        if not oracle.dispatches:
            # One honest failure beats a fabricated 0.0 (run 3's rule).
            out["status"] = "unvalidated"
            out["reason"] = "oracle observed no dispatches; structural term undefined"
            out["oracle_ran"] = False
            out["harness_score_v4"] = None
            out["struct_precision_dyn"] = None
            out["struct_recall_dyn"] = None
            return out
        t1 = time.time()
        blast = cpg.blast_radius({b for _, b in cpg.call_edges} or set(cpg.nodes))
        blast_ms = (time.time() - t1) * 1000 + 0.5
        prec = PROMOTE_MOD.precision_of(cpg.call_edges, oracle.dispatches)
        lat = max(0.0, 1 - blast_ms / 2000)
        ram = max(0.0, 1 - peak / 512)
        out.update({
            "oracle_ran": True,
            "struct_precision_dyn": round(prec, 4),
            "struct_recall_dyn": round(
                PROMOTE_MOD.recall_of(cpg.call_edges, oracle.dispatches), 4
            ),
            "blast_symbols": len(blast),
            "blast_latency_ms": round(blast_ms, 2),
            # Max 80, via the run-4 gate, so the ONLY thing that differs from
            # run 4 is the PIPELINE (dotted paths, unreferenced rule) and not the
            # arithmetic. The dead term is reported, never scored -- same decision
            # run 4 made, for the same reason.
            "harness_score_v4": round(
                GATE_MOD.gated_score(mermaid_validity(), prec, lat, ram), 2
            ),
            "dead_term_scored": False,
        })
    else:
        out["oracle_ran"] = False
        out["harness_score_v4"] = None
        out["score_withheld_reason"] = (
            "the structural term is defined against a dynamic oracle, and the "
            "oracle executes code. It is deliberately not run on a third-party "
            "tarball, so no harness_score is emitted for real repositories. The "
            "gated dead term and the certification counts ARE emitted, because "
            "they are trace-free."
        )
    if repo == "synthetic_taint_repo":
        truth = GROUND_TRUTH_DEAD
        out["ground_truth_dead"] = sorted(truth)
        out["false_positives"] = sorted(new_cert - truth)
        out["false_negatives"] = sorted(truth - new_cert)
        out["precision_vs_truth"] = (
            round(len(new_cert & truth) / len(new_cert), 4) if new_cert else 0.0
        )
        out["recall_vs_truth"] = (
            round(len(new_cert & truth) / len(truth), 4) if truth else 0.0
        )
        out["run4_false_positives"] = sorted(run4_cert - truth)
        out["ground_truth_checked"] = True
    else:
        out["ground_truth_checked"] = False
        out["ground_truth_note"] = (
            "no ground truth exists for a real repository, so the real-repo "
            "rows carry NO accuracy claim; the soundness claim is the proof in "
            "src/04_symbol_domain.py, and it is falsified or confirmed on "
            "synthetic_taint_repo where the truth is written down"
        )
    return out


def _hist(values):
    """Value -> count, most common first."""
    out = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def _dir_histogram(symbols):
    """Count symbols by their top-level dotted component, most common first."""
    hist = {}
    for s in symbols:
        hist[s.split(".", 1)[0]] = hist.get(s.split(".", 1)[0], 0) + 1
    return dict(sorted(hist.items(), key=lambda kv: (-kv[1], kv[0])))


def run_n9(repo):
    """N9: consumer-boundary gate. Two of N9's three mechanisms REFUTED here.

    Static only, and the dynamic oracle stays off third-party tarballs exactly as
    in run 7. The score-bearing path is NOT reimplemented: this calls
    ``run_n7`` and overlays the export-boundary measurements on top, so
    ``harness_score_v4`` is identical to run 7's BY CONSTRUCTION rather than by
    my re-deriving the arithmetic. ``scored_term_unchanged`` then checks the
    thing that actually matters -- that the certified set is unchanged too.
    """
    base = run_n7(repo)
    files, corpus, meta = load_repo_corpus(repo)
    cpg = CPG_MOD.build_cpg(files)
    dead = cpg.dead_symbols(dunder_exempt=True)
    counts = DOMAIN_MOD.token_name_counts(corpus.values())
    ident = DOMAIN_MOD.recount_identifiers_only(corpus.values())
    per_module = EXPORT_MOD.module_name_counts(corpus)
    witnesses = EXPORT_MOD.star_import_witnesses(corpus)
    exports = EXPORT_MOD.exported_names(corpus)

    run5_cert = DOMAIN_MOD.certify_unreferenced(dead, counts)
    closed = EXPORT_MOD.certify_dead_within_corpus(dead, counts, witnesses)
    per_mod = EXPORT_MOD.certify_per_module(dead, per_module)
    buckets = EXPORT_MOD.classify_dead(dead, counts, corpus)
    # Attribution runs over the WHOLE predicted-dead set. Over the blocked
    # remainder only, the export check upstream makes `dunder_all_declared`
    # unreachable and the instrument reports a structurally impossible zero.
    blockers = EXPORT_MOD.attribute_blockers(
        dead, corpus, per_module, counts, ident, exports
    )
    reason_counts = {r: 0 for r in EXPORT_MOD.BLOCKER_REASONS}
    for r in blockers.values():
        reason_counts[r] += 1

    out = dict(base)
    out.update({
        "variation": "n9_export_boundary",
        # The dead term is unscored, the certified set is unchanged, so the
        # metric DEFINITION is unchanged too. Bumping it would imply a new
        # denominator that does not exist.
        "metric_def": "unreferenced-domain-v4",
        "metric_def_note": (
            "UNCHANGED. N9 changes no scored term and, as measured below, no "
            "certified symbol. The export-boundary work is unscored reporting; "
            "max_metric stays 80 with the same denominator as runs 4 and 5."
        ),
        # -- H1: the star-import soundness hole
        "n_star_import_sites": EXPORT_MOD.count_star_import_sites(corpus),
        "n_star_target_modules": len([k for k in witnesses if not k.startswith("<")]),
        "n_unresolved_star_imports": len(
            [k for k in witnesses if k.startswith("<")]
        ),
        "n_modules_with_dunder_all": len(exports),
        "star_exposed_dead": sorted(EXPORT_MOD.star_exposed(dead, witnesses)),
        "closure_changed_run5": sorted(run5_cert - closed),
        "star_closure_is_noop": (run5_cert - closed) <= EXPORT_MOD.externally_driven(dead),
        # N9's surviving mechanism, split by evidence strength.
        "n_withheld_external_driver": len(EXPORT_MOD.externally_driven(dead)),
        "withheld_external_driver": sorted(EXPORT_MOD.externally_driven(dead))[:12],
        "external_driver_reasons": _hist(
            EXPORT_MOD.external_driver_reason(dead).values()
        ),
        "withheld_by_toplevel_dir": _dir_histogram(
            EXPORT_MOD.externally_driven(dead)
        ),
        "external_driver_adjudication": (
            "NOT executed. The driver (pytest, pytest-benchmark, CI) was not "
            "run, so these are withheld as externally-driven, not counted as "
            "measured false positives."
        ),
        # -- H2: N9's own fix, kept and labelled unsound
        "n_certified_run5": len(run5_cert),
        "n_certified_closed": len(closed),
        "n_certified_per_module_UNSOUND": len(per_mod),
        "per_module_extra_vs_global": sorted(per_mod - closed),
        # -- H3 + the taxonomy: what the other 80-98% actually is
        "n_predicted_dead": len(dead),
        "n_certified": len(closed),
        "n_publicly_exported": len(buckets["publicly_exported"]),
        "n_externally_driven_bucket": len(buckets["externally_driven"]),
        "n_blocked_by_mention": len(buckets["blocked_by_mention"]),
        "blocker_reasons": reason_counts,
        # Where the certificates actually LAND. On rich the certified set turned
        # out to be almost entirely `benchmarks/`, i.e. symbols invoked by an
        # external harness rather than by anything in the corpus -- the real
        # consumer boundary, and it is measurable as a directory concentration.
        "certified_by_toplevel_dir": _dir_histogram(closed),
        "n_certified_run5_by_toplevel_dir": _dir_histogram(run5_cert),
        "certified_dead": sorted(closed)[:12],
        "publicly_exported": sorted(buckets["publicly_exported"])[:12],
        "bucket_partition_is_exact": (
            len(buckets["certified_dead"])
            + len(buckets["publicly_exported"])
            + len(buckets["externally_driven"])
            + len(buckets["blocked_by_mention"])
            == len(dead)
        ),
        "blocked_sample": sorted(buckets["blocked_by_mention"])[:12],
        # -- the soundness claim H1 attacked, restated as a lemma
        "name_to_dispatch_lemma": EXPORT_MOD.name_to_dispatch_lemma(),
    })
    # Two DIFFERENT claims, previously conflated under one field name and worth
    # separating: the dead term is UNSCORED, so the harness score cannot move
    # (it is run 7's score by construction -- same code path, not a re-derivation),
    # while the REPORTED certified set does move, and that is the whole repair.
    out["harness_score_identical_to_run7"] = out.get("harness_score_v4") == base.get(
        "harness_score_v4"
    )
    out["scored_term_unchanged"] = True  # the dead term is not in the arithmetic
    out["certified_set_identical_to_run7"] = closed == run5_cert
    out["certified_removed_by_repair"] = sorted(run5_cert - closed)
    if repo == "synthetic_exports_repo":
        truth = GROUND_TRUTH_DEAD_EXPORTS
        out["ground_truth_dead"] = sorted(truth)
        out["ground_truth_checked"] = True
        # The dynamic oracle materialises modules by FLAT filename, so it cannot
        # execute a fixture with a real package layout -- `from lib.core import
        # *` resolves against a tmpdir holding `lib.core.py`. The structural term
        # is therefore undefined HERE, and the run's one `unvalidated` goes to
        # this row. It costs nothing: the dead term is trace-free and unscored,
        # and every N9 verdict is a dead-code verdict. The score-bearing row for
        # this run is synthetic_taint_repo, where the oracle does run.
        out["dead_term_validated"] = True
        out["h1_star_only_false_positive"] = sorted(
            {"lib.legacy.legacy_star_target"} & closed
        )
        out["h1_refuted"] = not ({"lib.legacy.legacy_star_target"} & closed)
        out["h2_per_module_false_positives"] = sorted(per_mod - truth)
        out["h2_per_module_recovers"] = sorted(per_mod & truth)
        for label, pred in (("global", closed), ("per_module", per_mod)):
            hits = len(pred & truth)
            out[f"{label}_precision_vs_truth"] = (
                round(hits / len(pred), 4) if pred else 0.0
            )
            out[f"{label}_recall_vs_truth"] = (
                round(hits / len(truth), 4) if truth else 0.0
            )
            out[f"{label}_false_positives"] = sorted(pred - truth)
            out[f"{label}_false_negatives"] = sorted(truth - pred)
        out["h3_direction_claim"] = (
            "N9 predicted reclassifying __all__ blockers would RAISE the "
            "certified count. certified_dead is a subset of run 5's set by "
            "construction (an export witness can only withhold), so the "
            "predicted direction is impossible. Measured: n_certified_run5 "
            f"{len(run5_cert)} -> n_certified_closed {len(closed)}."
        )
    else:
        out["ground_truth_checked"] = False
    return out


def run_n10(repo):
    """N10: out-of-corpus protocol dispatch, and the manifest N10 prescribes.

    Static, except for the three probes -- the fixture driver and the two real
    framework drivers -- which execute code and run on LOCAL fixtures and
    INSTALLED packages only. The dynamic oracle still never touches a
    third-party tarball.

    ``run_n9`` is called for the base row, so ``harness_score_v4`` is run 6's by
    construction rather than by re-deriving the arithmetic: the dead term is
    unscored and this node changes no scored term.

    Four rules, paired on the same graph and the same tokenisation:

      ``rule_r5``   run 5: ``occ[leaf] == 1`` over the repository corpus.
      ``rule_r6``   run 6: R5 minus the star-import lemma and the
                    external-driver conventions. The starting point.
      ``rule_r10a`` N10's prescription: R6 minus a hand-maintained manifest of
                    protocol method NAMES.
      ``rule_r10b`` the alternative that needs no hand list: R6 with the
                    occurrence count widened to the INSTALLED MODULES THE
                    REPOSITORY IMPORTS. Refuses (``None``) when that corpus is
                    incomplete.
    """
    base = run_n9(repo)
    files, corpus, meta = load_repo_corpus(repo)
    root = _fixture_dir(repo)
    t0 = time.time()
    cpg = CPG_MOD.build_cpg(files)
    dead = cpg.dead_symbols(dunder_exempt=True)
    counts = DOMAIN_MOD.token_name_counts(corpus.values())
    witnesses = EXPORT_MOD.star_import_witnesses(corpus)

    r5 = DOMAIN_MOD.certify_unreferenced(dead, counts)
    r6 = EXPORT_MOD.certify_dead_within_corpus(dead, counts, witnesses)
    manifest_blocked = PROTO_MOD.manifest_withheld(dead)
    r10a = r6 - manifest_blocked
    env_counts, env_meta = PROTO_MOD.env_reference_corpus(files, repo_root=root)
    r10b = PROTO_MOD.certify_with_env(dead, counts, env_counts, env_meta["env_complete"])

    out = dict(base)
    out.update({
        "variation": "n10_protocol_driver",
        "metric_def": "unreferenced-domain-v4",
        "max_metric": GATE_MOD.MAX_GATED_SCORE,
        "metric_def_note": (
            "UNCHANGED. The dead term remains UNSCORED, so harness_score_v4 is "
            "run 6's number by construction; what changes is the certified set."
        ),
        "harness_score_identical_to_run9": out.get("harness_score_v4") == base.get(
            "harness_score_v4"
        ),
        "n_predicted_dead": len(dead),
        # -- the environment corpus, with its CHECKED precondition
        "env_meta": env_meta,
        "env_precondition_ok": env_meta["env_complete"],
        "env_precondition_failure": env_meta["precondition_failure"],
        # -- the four rules, paired
        "rule_r5_n_certified": len(r5),
        "rule_r6_n_certified": len(r6),
        "rule_r10a_n_certified": len(r10a),
        "rule_r10b_n_certified": (len(r10b) if r10b is not None else None),
        "rule_r10b_status": "scored" if r10b is not None else "refused",
        "certified_r5": sorted(r5)[:12],
        "certified_r6": sorted(r6)[:12],
        "certified_r10a": sorted(r10a)[:12],
        "certified_r10b": (sorted(r10b)[:12] if r10b is not None else None),
        "r10a_removed_vs_r6": len(r6 - r10a),
        "r10b_removed_vs_r6": (len(r6 - r10b) if r10b is not None else None),
        # -- the manifest's price, on the manifest's own terms
        "manifest_is_approximation": True,
        "manifest_size": len(PROTO_MOD.PROTOCOL_NAMES),
        "manifest_blocked_total": len(manifest_blocked),
        "manifest_blocked_by_dir": _dir_histogram(manifest_blocked),
        # -- leakage: how often the environment mentions each candidate name.
        # Reported so a rule that certifies nothing because EVERY name collides
        # can never be mistaken for a rule that certifies nothing because it is
        # right.
        "env_occurrences_for_predicted_dead": _hist(
            f"{env_counts.get(DOMAIN_MOD.bare(s), 0)}" for s in sorted(dead)
        ),
        "n_blocked_by_env_alone": len({
            s for s in r6 if env_counts.get(DOMAIN_MOD.bare(s), 0) > 0
        }),
        "peak_ram_mb": round(peak_rss_mb(), 2),
        "token_cost_usd": 0.0,
        "elapsed_s": round(time.time() - t0, 2),
    })
    # -- per-symbol adjudication: which rule certified what, and why not. The
    # reviewer's objection to an aggregate is right, so the aggregate is not the
    # headline; this table is.
    env_only_block = {
        s for s in r6 if env_counts.get(DOMAIN_MOD.bare(s), 0) > 0
    }
    out["withheld_reasons"] = {
        s: ("manifest_name" if s in manifest_blocked else "")
        + ("|" if s in manifest_blocked and s in env_only_block else "")
        + ("env_occurrence" if s in env_only_block else "")
        for s in sorted((manifest_blocked | env_only_block) & dead)
    }
    out["r10a_vs_r10b_comparable"] = (
        None if r10b is None else (r10a <= r10b, r10b <= r10a)
    )
    out["n_certified_by_both"] = (
        None if r10b is None else len(r10a & r10b)
    )
    out["only_r10a"] = None if r10b is None else sorted(r10a - r10b)[:12]
    # The four names run 6 recorded as unadjudicated residuals, looked up in the
    # environment corpus of THIS repository. Stated as counts so the reader can
    # see whether the framework that dispatches them is reachable from the repo's
    # own imports (hole B) or not (hole A).
    out["env_occurrence_of_run6_residuals"] = {
        n: env_counts.get(n, 0)
        for n in ("emit", "flush", "process_bind_param", "process_result_value",
                  "coerce_compared_value")
    }
    out["residual_names_visible_in_env"] = sorted(
        n for n, c in out["env_occurrence_of_run6_residuals"].items() if c > 0
    )
    # Whether the automatic alternative to a hand manifest -- scan the WHOLE
    # environment -- is admissible at all on this machine. Measured, not argued.
    out["whole_env_admissibility"] = PROTO_MOD.whole_env_admissibility()
    out["only_r10b"] = None if r10b is None else sorted(r10b - r10a)[:12]

    if repo == "synthetic_protocol_repo":
        probe = PROTO_MOD.fixture_driver_probe(
            root, "experiments/fixtures/synthetic_protocol_driver"
        )
        truth = GROUND_TRUTH_DEAD_PROTOCOL
        verdict = PROTO_MOD.adjudicate(
            dead, truth, {"rule_r5": r5, "rule_r6": r6, "rule_r10a": r10a, "rule_r10b": r10b}
        )
        out["fixture_driver_probe"] = probe
        out["executed_live"] = sorted(probe.get("reached_sentinels", []))
        out["executed_live_symbols"] = sorted(
            s.replace("alpha.T.", "alpha.T.") for s in probe.get("reached_sentinels", [])
        )
        out["ground_truth_dead"] = sorted(truth)
        out["ground_truth_checked"] = True
        out["adjudication"] = verdict
        out["manifest_missed_live_symbols"] = sorted(
            set(out["executed_live"]) & set(r10a)
        )
        out["fixture_env_occurrence"] = {
            s: env_counts.get(DOMAIN_MOD.bare(s), 0)
            for s in sorted(truth | set(out["executed_live"]))
        }
        out["n_immune_dead_symbols"] = sum(
            1 for s in truth if env_counts.get(DOMAIN_MOD.bare(s), 0) == 0
        )
        out["real_framework_probes"] = PROTO_MOD.real_framework_probes()
    else:
        out["ground_truth_checked"] = False
    return out


def run_one(variation, repo):
    if variation == "n10_protocol_driver":
        return run_n10(repo)
    if variation == "n9_export_boundary":
        return run_n9(repo)
    if variation == "n7_symbol_domain":
        return run_n7(repo)
    if variation == "v3_trace_informed_cpg":
        return run_v3(repo)
    tracemalloc.start()
    t0 = time.time()
    files = load_repo_files(repo)
    g_imp, g_call = ground_truth_edges(files)
    dyn = {}
    if variation == "v0_baseline_linear":
        p_imp, p_call = naive_regex_edges(files)
        validity = mermaid_validity()
        tokens_usd = 0.002 * len(files)
        # Run 4: v0's dead_code_acc is a HARDCODED 0.5 (see the
        # `synthetic_bad_repo` special case below), so it is not a measurement
        # at all -- a strictly worse defect than run 2's, which at least
        # measured something. It carries no certification and is removed from
        # the gated scale for the same reason as the others.
        dyn["assessment_v3"] = {
            "dead_predicted": None,
            "dead_certified": [],
            "dead_unadjudicable": None,
            "dead_term_v3": 0.0,
            "dead_code_acc_strict": None,
            "dead_term_defect": "hardcoded constant, not measured",
            "n_certified": 0,
            "n_predicted_dead": None,
            "structural_identifiable": False,
            "harness_score_v3": None,
            "max_score_v3": GATE_MOD.MAX_GATED_SCORE,
            "in_sample": True,
        }
    elif variation == "v2_treesitter_cpg":
        cpg = CPG_MOD.build_cpg(files)
        oracle = DYN_MOD.run_oracle(files)
        p_imp, p_call = cpg.import_edges, cpg.call_edges
        validity = mermaid_validity()
        tokens_usd = 0.0  # deterministic static analysis: no model in the loop
        # Governance payload: what a change to any resolved callee endangers.
        t1 = time.time()
        seeds = {b for _, b in cpg.call_edges} or set(cpg.nodes)
        blast = cpg.blast_radius(seeds)
        blast_ms = (time.time() - t1) * 1000 + 0.5
        dead_pred = cpg.dead_symbols(dunder_exempt=True)
        coarse_oracle = degrade_to_coarse(oracle.dispatches)
        cpg_coarse = degrade_to_coarse(cpg.call_edges)
        v0_coarse = naive_regex_calls(files)
        dyn = {
            "metric_def": "dynamic-oracle-v1",
            "oracle_dispatches": len(oracle.dispatches),
            "oracle_invoked": sorted(oracle.invoked),
            "oracle_import_failed": oracle.import_failed,
            "cpg_resolution_rate": round(cpg.resolution_rate(), 4),
            "cpg_unresolved": sorted(cpg.unresolved),
            "cpg_cycles": sorted(cpg.cyclic_symbols()),
            "struct_precision_dyn": round(oracle.precision(cpg.call_edges), 4),
            "struct_recall_dyn": round(oracle.recall(cpg.call_edges), 4),
            "struct_false_edges": sorted(map(list, oracle.false_edges(cpg.call_edges))),
            "struct_missed": sorted(map(list, oracle.missed(cpg.call_edges))),
            "dead_predicted": sorted(dead_pred),
            "dead_confirmed": sorted(oracle.confirmed_dead(dead_pred)),
            "blast_symbols": len(blast),
            # v0's prediction is already coarse; degrading it again would
            # silently drop every pair and report a fabricated 0.0.
            "coarse_precision_v0_space": round(
                len(coarse_oracle & v0_coarse) / max(1, len(v0_coarse)), 4
            ),
            "coarse_precision_cpg_space": round(
                len(coarse_oracle & cpg_coarse) / max(1, len(cpg_coarse)), 4
            ),
            "coarse_truth_size": len(coarse_oracle),
            "coarse_v0_size": len(v0_coarse),
        }
        # Honest structural term: precision against an oracle that never saw
        # the parser. Legacy static F1 is deliberately NOT reported for v2 --
        # scoring an AST-based predictor against an AST-based truth yields 1.0
        # and measures nothing (equations.md row 1).
        structural_f1 = None
        dead_acc = (
            len(dyn["dead_confirmed"]) / len(dead_pred) if dead_pred else 1.0
        )
        # Run 4: v2 under the corrected definition. The full oracle is its own
        # single fold, so this row is IN-SAMPLE and is not comparable to the
        # held-out rows -- it is here to show what the 20 removed points were
        # contributing, not to be ranked against anything.
        peak_pre = peak_rss_mb()
        lat_pre = max(0.0, 1 - blast_ms / 2000)
        ram_pre = max(0.0, 1 - peak_pre / 512)
        dyn["assessment_v3"] = dict(
            GATE_MOD.assess(cpg, oracle.dispatches, oracle.covered_symbols(),
                            1.0, lat_pre, ram_pre),
            in_sample=True,
        )
    else:
        # Placeholders driver iterations replace with real variation impls.
        p_imp, p_call = naive_regex_edges(files)
        validity, tokens_usd = 0.0, 0.0
    if variation != "v2_treesitter_cpg":
        imp_f1 = f1(p_imp, g_imp)
        call_f1 = f1(p_call, g_call)
        structural_f1 = (imp_f1 + call_f1) / 2
        # blast-radius latency proxy: reverse-reachability over call edges
        t1 = time.time()
        succ = {}
        for a, b in p_call:
            succ.setdefault(b, set()).add(a)
        _ = succ.get("fetch", set())
        blast_ms = (time.time() - t1) * 1000 + 0.5
        # dead-code proxy on synthetic fixture: dead_method never called
        dead_acc = 1.0 if repo == "synthetic_bad_repo" and ("repo.py", "dead_method") not in p_call else 0.5
    peak = peak_rss_mb()
    lat_score = max(0.0, 1 - blast_ms / 2000)
    ram_score = max(0.0, 1 - peak / 512)
    struct_term = dyn["struct_precision_dyn"] if variation == "v2_treesitter_cpg" else structural_f1
    score = 30 * validity + 30 * struct_term + 20 * dead_acc + 10 * lat_score + 10 * ram_score
    current, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    gc.collect()
    out = {
        "variation": variation, "repo": repo, "files": len(files),
        "mermaid_validity_rate": round(validity, 4),
        "structural_f1_static": None if structural_f1 is None else round(structural_f1, 4),
        "blast_latency_ms": round(blast_ms, 2), "peak_ram_mb": round(peak, 2),
        "tracemalloc_kb": round(current / 1024, 1), "token_cost_usd": round(tokens_usd, 4),
        "dead_code_acc": round(dead_acc, 4), "harness_score": round(score, 2),
        "elapsed_s": round(time.time() - t0, 2),
    }
    out.update(dyn)
    if variation == "v2_treesitter_cpg":
        v3 = dyn["assessment_v3"]
        out["metric_def_v3"] = "certified-dead-v3"
        out["harness_score_v3"] = v3["harness_score_v3"]
        out["max_score_v3"] = GATE_MOD.MAX_GATED_SCORE
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variation", default="v0_baseline_linear", choices=VARIATIONS)
    ap.add_argument("--repo", default="synthetic_bad_repo")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--pair", action="store_true",
                    help="also run the v0 baseline on the same repo for a paired comparison")
    args = ap.parse_args()
    if args.list:
        print(json.dumps({"variations": VARIATIONS, "repos": list(REPOS)}))
        return
    repos = list(REPOS) if args.repo == "all" else [args.repo]
    results = []
    for r in repos:
        results.append(run_one(args.variation, r))
        if args.pair:
            results.append(run_one("v0_baseline_linear", r))
    os.makedirs("experiments", exist_ok=True)
    out = args.out or f"experiments/run-{args.variation}-{int(time.time())}.log"
    with open(out, "w") as fh:
        json.dump(results, fh, indent=2)
    print(json.dumps(results, indent=2))
    log.info("wrote %s", out)


if __name__ == "__main__":
    main()
