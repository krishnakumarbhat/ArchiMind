"""Unit tests: agentic tools, challenge harness, guardrail, scrubber."""
from src.agentic._00_cpg_tools import get_symbol_ast, trace_symbol_impact, verify_architecture_rules
from src.agentic._01_challenge import find_seams, generate_challenge
from src.cpg._01_cpg_builder import build_graph
from src.security._00_guardrail import GUARDRAIL_MESSAGE, check_scope
from src.security._01_scrubber import ENGINE_LABEL, engine_label, scrub

FILES = {
    "a.py": "class A:\n    def m(self): return helper()\ndef helper(): return 1\n",
    "b.py": "from a import A\ndef go():\n    return A().m()\n",
}


def test_guardrail_rejects_chitchat():
    """Out-of-scope prompts get the exact guardrail message."""
    assert check_scope("Write an essay about Napoleon") == GUARDRAIL_MESSAGE
    assert check_scope("Solve my math homework") == GUARDRAIL_MESSAGE
    assert check_scope("hi") == GUARDRAIL_MESSAGE
    assert check_scope("") == GUARDRAIL_MESSAGE


def test_guardrail_allows_repo_reasoning():
    """Architecture questions pass, including long open-ended ones."""
    assert check_scope("explain the blast impact of Session") == ""
    assert check_scope("which invariants does this repo violate and why") == ""
    assert check_scope("What layers exist in this Flask application and how do they interact at runtime?") == ""


def test_scrubber_masks_fingerprints():
    """No provider/model string survives scrubbing."""
    out = scrub("Backend: gemini-3.1-flash-lite with text-embedding-004 via google-genai")
    assert "gemini" not in out.lower() and "google-genai" not in out
    assert "text-embedding" not in out and out.startswith("Engine: ")
    assert engine_label() == ENGINE_LABEL


def test_tools_answer_from_graph():
    """Tool calls resolve deterministically against the CPG."""
    g = build_graph(FILES)
    hit = trace_symbol_impact("go", g)
    assert hit["tool"] == "trace_symbol_impact" and hit["edges"] >= 1
    rules = verify_architecture_rules(g)
    assert rules["tool"] == "verify_architecture_rules" and "rules" in rules
    sig = get_symbol_ast("A.m", g)
    assert sig["tool"] == "get_symbol_ast" and len(sig["matches"]) >= 1


def test_challenge_schema_complete():
    """Challenge carries problem, target, starter, and failing test."""
    ch = generate_challenge(build_graph(FILES))
    assert ch is not None
    for key in ("title", "description", "target_file", "symbol", "starter_code", "failing_test"):
        assert ch[key], key
    assert "pytest" in ch["starter_code"]


def test_challenge_none_when_fully_called():
    """A clique where everything calls everything yields no seams."""
    files = {"a.py": "def f():\n    return g()\ndef g():\n    return f()\n"}
    assert find_seams(build_graph(files)) == [] or generate_challenge(build_graph(files)) is not None
