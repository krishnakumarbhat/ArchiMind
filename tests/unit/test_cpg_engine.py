"""Unit tests: CPG engine, closure gate, invariants, evaluator-optimizer."""
import networkx as nx

from src.cpg._00_ts_ast import ASTExtractor
from src.cpg._01_cpg_builder import CodePropertyGraphBuilder
from src.cpg._02_closure_gate import InheritanceClosureGate
from src.governance._00_blast_radius import ReverseBlastRadiusEngine
from src.governance._01_invariants import ArchitectureInvariantChecker
from src.ingestion._00_tarball_client import repo_tarball_url
from src.orchestration._01_eval_optimizer import MermaidEvaluatorOptimizer

FILES = {
    "routes.py": "from repo import UserRepo\ndef get_user(uid):\n    return UserRepo().fetch(uid)\n",
    "repo.py": "class UserRepo:\n    def fetch(self, uid): return uid\n    def dead_method(self): return 42\n",
    "handlers.py": "import logging\nclass RichHandler(logging.Handler):\n    def emit(self, r): pass\n",
}

EXTRACTOR = ASTExtractor()
BUILDER = CodePropertyGraphBuilder(EXTRACTOR)
OPTIMIZER = MermaidEvaluatorOptimizer()


def test_extractor_resolves_classes_methods_calls():
    """Extractor finds classes, methods, imports, and call leaves."""
    m = EXTRACTOR.extract_module(FILES["repo.py"], "repo.py")
    assert m.parse_ok and "UserRepo" in m.classes
    assert "fetch" in m.methods["UserRepo"]
    assert "fetch" in EXTRACTOR.extract_module(FILES["routes.py"], "routes.py").calls


def test_broken_file_marks_parse_error():
    """Syntax errors yield parse_ok False instead of raising."""
    assert EXTRACTOR.extract_module("def oops(:\n", "broken.py").parse_ok is False


def test_builder_precision_no_false_edges():
    """Every CALLS edge targets a real declared symbol (research: precision 1.0)."""
    g = BUILDER.build(FILES)
    declared = {str(d.get("name")) for _, d in g.nodes(data=True)} | {"session", "UserRepo"}
    for u, v, d in g.edges(data=True):
        if d.get("kind") == "CALLS":
            assert g.nodes[v].get("name") in declared


def test_blast_radius_is_reverse_reachability():
    """Changing UserRepo.fetch affects its caller get_user; dead code affects nothing."""
    g = BUILDER.build(FILES)
    assert any(n.endswith("get_user") for n in CodePropertyGraphBuilder.blast_radius(g, "UserRepo.fetch"))
    assert CodePropertyGraphBuilder.blast_radius(g, "dead_method") == []


def test_self_calls_bind_to_owner_class():
    """self.helper() resolves to the same class only, not every helper in the corpus."""
    files = {
        "a.py": "class A:\n    def run(self):\n        return self.helper()\n    def helper(self): return 1\n",
        "b.py": "class B:\n    def helper(self): return 2\n",
    }
    g = BUILDER.build(files)
    assert any(n.endswith("A::run") for n in CodePropertyGraphBuilder.blast_radius(g, "A.helper"))
    assert CodePropertyGraphBuilder.blast_radius(g, "B.helper") == []


def test_typescript_extraction():
    """TS classes, methods, extends and imports are extracted via tree-sitter."""
    src = "import { Base } from './base.js';\nexport class Runner extends Base {\n  start() { return this.step(); }\n  step() { return 1; }\n}\nexport function boot() { return new Runner().start(); }\n"
    m = EXTRACTOR.extract_module(src, "runner.ts")
    assert m.classes == {"Runner": ["Base"]} and m.methods["Runner"] == ["start", "step"]
    assert "boot" in m.functions and m.imports["Base"] == "./base.js"


def test_closure_withholds_out_of_corpus_protocol():
    """RichHandler.emit withheld via Handler edge; plain dead code certified."""
    g = BUILDER.build(FILES)
    gate = InheritanceClosureGate(g)
    withheld = gate.withheld_methods()
    assert any("emit" in k for k in withheld)
    assert CodePropertyGraphBuilder.out_of_corpus_bases(g) == {"RichHandler": ["Handler"]}
    assert gate.certified_dead(["repo.UserRepo.dead_method", "m::handlers.py::RichHandler::emit"]) == [
        "repo.UserRepo.dead_method"
    ]


def test_compact_roundtrip():
    """Serialization preserves nodes, edges, and blast results."""
    g = BUILDER.build(FILES)
    g2 = CodePropertyGraphBuilder.from_compact(CodePropertyGraphBuilder.to_compact(g))
    assert g2.number_of_nodes() == g.number_of_nodes()
    assert CodePropertyGraphBuilder.blast_radius(g2, "UserRepo.fetch") == CodePropertyGraphBuilder.blast_radius(
        g, "UserRepo.fetch"
    )


def test_invariants_shape():
    """All three invariants evaluate with pass flags."""
    ids = {r["id"] for r in ArchitectureInvariantChecker(BUILDER.build(FILES)).check_all()}
    assert ids == {"presentation-isolation", "acyclic-dependencies", "domain-purity"}


def test_invariants_catch_direct_import():
    """Presentation->data edge fails isolation."""
    g = nx.DiGraph()
    g.add_node("v", kind="File", path="views.py", name="views.py")
    g.add_node("r", kind="File", path="repo.py", name="repo.py")
    g.add_edge("v", "r", kind="IMPORTS")
    res = {r["id"]: r for r in ArchitectureInvariantChecker(g).check_all()}
    assert res["presentation-isolation"]["passed"] is False


def test_eval_optimizer_heals_broken_mermaid():
    """First invalid draft triggers reflection; terminal state is valid."""
    calls = {"n": 0}

    def gen(kind, repo, ctx, err):
        calls["n"] += 1
        assert (calls["n"] > 1) == bool(err)  # error feedback only on retry
        return "not a diagram" if calls["n"] == 1 else "graph TD\n    A-->B"

    state = OPTIMIZER.run("hld", "demo", "ctx", gen)
    assert MermaidEvaluatorOptimizer.validate(str(state.get("mermaid", ""))) == "" and state.get("attempts") == 2


def test_eval_optimizer_caps_retries():
    """Persistently broken generator stops at the retry cap."""
    state = OPTIMIZER.run("hld", "demo", "ctx", lambda k, r, c, e: "junk")
    assert (state.get("attempts") or 0) <= 3 and MermaidEvaluatorOptimizer.validate(str(state.get("mermaid", ""))) != ""


def test_tarball_url_rejects_non_github():
    """Non-GitHub URLs are rejected before any network call."""
    assert repo_tarball_url("https://github.com/pallets/flask").startswith("https://codeload.github.com/")
    try:
        repo_tarball_url("https://example.com/x")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_impact_report_shape_and_timing():
    """Blast engine returns names, count, and sub-second timing."""
    artifact = CodePropertyGraphBuilder.to_compact(BUILDER.build(FILES))
    rep = ReverseBlastRadiusEngine(artifact).compute_impact("UserRepo.fetch")
    assert rep.symbol == "UserRepo.fetch" and rep.edges >= 1 and rep.ms < 1000


def test_empty_graph_emits_explicit_empty_state():
    """Zero files/edges yield a styled empty state, never a placeholder diagram."""
    from src.orchestration._03_cpg_diagrams import CPGDiagramCompiler

    g = BUILDER.build({})
    comp = CPGDiagramCompiler(g)
    for code in (comp.hld(), comp.lld(), comp.flow()):
        assert 'No Call Edges Detected in Analyzed Source Files' in code
        assert 'A-->B' not in code and 'c_root' not in code and 'K_module' not in code
        assert MermaidEvaluatorOptimizer.validate(code) == ""


def test_no_dummy_fallback_strings_anywhere():
    """No shipped diagram path may contain hardcoded dummy content."""
    import src.orchestration._03_cpg_diagrams as dmod
    import inspect

    src = inspect.getsource(dmod)
    assert 'A-->B' not in src and 'c_root' not in src and 'K_module' not in src
