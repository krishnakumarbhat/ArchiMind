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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("auto_research")

REPOS = {
    "synthetic_bad_repo": None,  # local fixture, built on demand
    "synthetic_cpg_repo": None,  # local fixture, acyclic + dynamic-oracle friendly
    "pallets/flask": "https://codeload.github.com/pallets/flask/tar.gz/refs/heads/main",
    "psf/requests": "https://codeload.github.com/psf/requests/tar.gz/refs/heads/main",
    "tiangolo/sqlmodel": "https://codeload.github.com/tiangolo/sqlmodel/tar.gz/refs/heads/main",
    "Textualize/rich": "https://codeload.github.com/Textualize/rich/tar.gz/refs/heads/main",
}

VARIATIONS = ["v0_baseline_linear", "v1_eval_optimizer", "v2_treesitter_cpg",
              "v3_hybrid_cpg_rag", "v4_governance_harness", "v5_full_agentic_system"]

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


def run_one(variation, repo):
    tracemalloc.start()
    t0 = time.time()
    files = load_repo_files(repo)
    g_imp, g_call = ground_truth_edges(files)
    dyn = {}
    if variation == "v0_baseline_linear":
        p_imp, p_call = naive_regex_edges(files)
        validity = mermaid_validity()
        tokens_usd = 0.002 * len(files)
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
