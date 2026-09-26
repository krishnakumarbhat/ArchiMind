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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("auto_research")

REPOS = {
    "synthetic_bad_repo": None,  # local fixture, built on demand
    "synthetic_cpg_repo": None,  # local fixture, acyclic + dynamic-oracle friendly
    "synthetic_promo_repo": None,  # local fixture, disjoint callers across folds
    "pallets/flask": "https://codeload.github.com/pallets/flask/tar.gz/refs/heads/main",
    "psf/requests": "https://codeload.github.com/psf/requests/tar.gz/refs/heads/main",
    "tiangolo/sqlmodel": "https://codeload.github.com/tiangolo/sqlmodel/tar.gz/refs/heads/main",
    "Textualize/rich": "https://codeload.github.com/Textualize/rich/tar.gz/refs/heads/main",
}

VARIATIONS = ["v0_baseline_linear", "v1_eval_optimizer", "v2_treesitter_cpg",
              "v3_trace_informed_cpg", "v3_hybrid_cpg_rag",
              "v4_governance_harness", "v5_full_agentic_system"]

SKIP_DIRS = {"tests", "test", "docs", "examples", "vendor", "node_modules", ".git", "__pycache__"}
SKIP_EXT = {".png", ".jpg", ".mp4", ".gif", ".ico", ".woff", ".ttf", ".bin", ".so"}
MAX_FILE_BYTES = 200_000
MAX_FILES = 400

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


def load_repo_files(repo):
    if repo == "synthetic_bad_repo":
        root = build_synthetic_fixture()
        out = {}
        for name in os.listdir(root):
            if name.endswith(".py"):
                with open(os.path.join(root, name)) as fh:
                    out[name] = fh.read()
        return out
    if repo == "synthetic_cpg_repo":
        root = build_cpg_fixture()
        out = {}
        for name in os.listdir(root):
            if name.endswith(".py"):
                with open(os.path.join(root, name)) as fh:
                    out[name] = fh.read()
        return out
    if repo == "synthetic_promo_repo":
        root = build_promo_fixture()
        out = {}
        for name in os.listdir(root):
            if name.endswith(".py"):
                with open(os.path.join(root, name)) as fh:
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


def run_one(variation, repo):
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
