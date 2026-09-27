"""Mermaid v11 conformance: validator must reject what browsers reject.

Regression source: analysis of github.com/LeevAI-Devs/webpage produced
`Init[init()]` (v11 flowchart parse error) and literal-\\n payloads while the
old validator passed them, so the repair loop never fired (repair_log 1/1/1).
"""
from src.orchestration._01_eval_optimizer import normalize_mermaid, validate_mermaid

FLOW_SAMPLE = (
    "graph TD; Browser[Browser Load] --> Constructor[LeevAIWebsite Constructor]; "
    "Constructor --> Init[init()]; Init --> Setup[setup()]; "
    "Navigate[navigateTo(page)] --> Redirect[Window Location Change];"
)


def test_validator_rejects_parens_in_flowchart_labels():
    """v11 fails on Init[init()]; the validator must flag it pre-render."""
    assert "parentheses" in validate_mermaid(FLOW_SAMPLE)


def test_normalize_makes_flow_sample_valid():
    """Entity-encoded labels pass the validator (verified RENDER_OK in v11)."""
    fixed = normalize_mermaid(FLOW_SAMPLE)
    assert "init()" not in fixed and "#40;" in fixed
    assert validate_mermaid(fixed) == ""


def test_validator_rejects_escaped_newlines():
    """Double-encoded payloads (literal backslash-n, zero real newlines) must not pass."""
    assert "escaped newlines" in validate_mermaid("sequenceDiagram\\nparticipant A\\nA->>B: hi")


def test_normalize_unescapes_newlines():
    """Unescaped payloads validate once real newlines are restored."""
    fixed = normalize_mermaid("sequenceDiagram\\nparticipant A\\nA->>B: hi")
    assert validate_mermaid(fixed) == ""


def test_validator_rejects_unbalanced_brackets():
    """Truncated labels with unbalanced brackets fail fast with a clear message."""
    assert "unbalanced" in validate_mermaid("graph TD\n    A[open --> B")


def test_numeric_entities_allowed():
    """The validator must not flag its own #40; / #41; entity codes."""
    assert validate_mermaid("graph TD\n    A[init#40;#41;] --> B") == ""
