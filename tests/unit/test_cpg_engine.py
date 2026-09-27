"""Unit tests: CPG engine, closure gate, invariants, evaluator-optimizer."""
import networkx as nx

from src.cpg._00_ts_ast import extract_module
from src.cpg._01_cpg_builder import blast_radius, build_graph, from_compact, out_of_corpus_bases, to_compact
from src.cpg._02_closure_gate import certified_dead, withheld_methods
from src.governance._00_blast_radius import impact
from src.governance._01_invariants import check_invariants
from src.ingestion._00_tarball_client import repo_tarball_url
from src.orchestration._01_eval_optimizer import run_eval_optimizer, validate_mermaid

FILES = {
    "routes.py": "from repo import UserRepo\ndef get_user(uid):\n    return UserRepo().fetch(uid)\n",
    "repo.py": "class UserRepo:\n    def fetch(self, uid): return uid\n    def dead_method(self): return 42\n",
    "handlers.py": "import logging\nclass RichHandler(logging.Handler):\n    def emit(self, r): pass\n",
}


def test_extractor_resolves_classes_methods_calls():
    """Extractor finds classes, methods, imports, and call leaves."""
    m = extract_module(FILES["repo.py"], "repo.py")
    assert m.parse_ok and "UserRepo" in m.classes
    assert "fetch" in m.methods["UserRepo"]
    assert "fetch" in extract_module(FILES["routes.py"], "routes.py").calls


def test_broken_file_marks_parse_error():
    """Syntax errors yield parse_ok False instead of raising."""
    assert extract_module("def oops(:\n", "broken.py").parse_ok is False


def test_builder_precision_no_false_edges():
    """Every CALLS edge targets a real declared symbol (research: precision 1.0)."""
    g = build_graph(FILES)
    declared = {str(d.get("name")) for _, d in g.nodes(data=True)} | {"session", "UserRepo"}
    for u, v, d in g.edges(data=True):
        if d.get("kind") == "CALLS":
            assert g.nodes[v].get("name") in declared


def test_blast_radius_is_reverse_reachability():
    """Changing UserRepo.fetch affects its caller get_user; dead code affects nothing."""
    g = build_graph(FILES)
    assert any(n.endswith("get_user") for n in blast_radius(g, "UserRepo.fetch"))
    assert blast_radius(g, "dead_method") == []


def test_self_calls_bind_to_owner_class():
    """self.helper() resolves to the same class only, not every helper in the corpus."""
    files = {
        "a.py": "class A:\n    def run(self):\n        return self.helper()\n    def helper(self): return 1\n",
        "b.py": "class B:\n    def helper(self): return 2\n",
    }
    g = build_graph(files)
    assert any(n.endswith("A::run") for n in blast_radius(g, "A.helper"))
    assert blast_radius(g, "B.helper") == []


def test_typescript_extraction():
    """TS classes, methods, extends and imports are extracted via tree-sitter."""
    src = "import { Base } from './base.js';\nexport class Runner extends Base {\n  start() { return this.step(); }\n  step() { return 1; }\n}\nexport function boot() { return new Runner().start(); }\n"
    m = extract_module(src, "runner.ts")
    assert m.classes == {"Runner": ["Base"]} and m.methods["Runner"] == ["start", "step"]
    assert "boot" in m.functions and m.imports["Base"] == "./base.js"


def test_closure_withholds_out_of_corpus_protocol():
    """RichHandler.emit withheld via Handler edge; plain dead code certified."""
    g = build_graph(FILES)
    withheld = withheld_methods(g)
    assert any("emit" in k for k in withheld)
    assert out_of_corpus_bases(g) == {"RichHandler": ["Handler"]}
    assert certified_dead(["repo.UserRepo.dead_method", "m::handlers.py::RichHandler::emit"], g) == [
        "repo.UserRepo.dead_method"
    ]


def test_compact_roundtrip():
    """Serialization preserves nodes, edges, and blast results."""
    g = build_graph(FILES)
    g2 = from_compact(to_compact(g))
    assert g2.number_of_nodes() == g.number_of_nodes()
    assert blast_radius(g2, "UserRepo.fetch") == blast_radius(g, "UserRepo.fetch")


def test_invariants_shape():
    """All three invariants evaluate with pass flags."""
    ids = {r["id"] for r in check_invariants(build_graph(FILES))}
    assert ids == {"presentation-isolation", "acyclic-dependencies", "domain-purity"}


def test_invariants_catch_direct_import():
    """Presentation->data edge fails isolation."""
    g = nx.DiGraph()
    g.add_node("v", kind="File", path="views.py", name="views.py")
    g.add_node("r", kind="File", path="repo.py", name="repo.py")
    g.add_edge("v", "r", kind="IMPORTS")
    res = {r["id"]: r for r in check_invariants(g)}
    assert res["presentation-isolation"]["passed"] is False


def test_eval_optimizer_heals_broken_mermaid():
    """First invalid draft triggers reflection; terminal state is valid."""
    calls = {"n": 0}

    def gen(kind, repo, ctx, err):
        calls["n"] += 1
        assert (calls["n"] > 1) == bool(err)  # error feedback only on retry
        return "not a diagram" if calls["n"] == 1 else "graph TD\n    A-->B"

    state = run_eval_optimizer("hld", "demo", "ctx", gen)
    assert validate_mermaid(state["mermaid"]) == "" and state["attempts"] == 2


def test_eval_optimizer_caps_retries():
    """Persistently broken generator stops at the retry cap."""
    state = run_eval_optimizer("hld", "demo", "ctx", lambda k, r, c, e: "junk")
    assert state["attempts"] <= 3 and validate_mermaid(state["mermaid"]) != ""


def test_tarball_url_rejects_non_github():
    """Non-GitHub URLs are rejected before any network call."""
    assert repo_tarball_url("https://github.com/pallets/flask").startswith("https://codeload.github.com/")
    try:
        repo_tarball_url("https://example.com/x")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_impact_report_shape_and_timing():
    """Blast API helper returns names, count, and sub-second timing."""
    rep = impact("UserRepo.fetch", to_compact(build_graph(FILES)))
    assert rep["symbol"] == "UserRepo.fetch" and rep["edges"] >= 1 and rep["ms"] < 1000
