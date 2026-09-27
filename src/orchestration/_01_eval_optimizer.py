"""Cyclic LangGraph evaluator-optimizer for Mermaid synthesis.

Purpose: turn single-shot diagram generation into a self-healing loop:
generator drafts -> deterministic validator checks -> reflection repairs
(capped at MERMAID_MAX_RETRIES). Guarantees renderable output or an explicit
failure instead of silently broken markup.
"""
import logging
import re
from typing import Callable, Dict, Optional

from src.config._00_settings import SETTINGS
from src.orchestration._00_agent_state import DiagramState

logger = logging.getLogger(__name__)

GenerateFn = Callable[[str, str, str, Optional[str]], str]  # (kind, repo, ctx, err) -> mermaid

_MERMAID_BAD = re.compile(r"```|<script|\{\{|\}\}|\[\[|\]\]|#(?!\d+;)")

_PAREN_IN_LABEL = re.compile(r"\[[^\[\]\n]*[()][^\[\]\n]*\]")
_SUBGRAPH_TITLE = re.compile(r"(?m)^\s*subgraph\s+([A-Za-z0-9_]+)\s+\[([^\]]+)\]")


def normalize_mermaid(code: str) -> str:
    """Make LLM output parseable before validation.

    - Unescape literal backslash-n sequences (double-encoded JSON payloads).
    - Quote bare subgraph titles: v11 rejects `subgraph Id [Words Here]`.
    - Entity-encode parentheses inside [...] labels: v11 flowchart chokes on
      `Init[init()]` (expects shape-end, finds `)`).
    """
    text = (code or "").replace("\\r\n", "\n").replace("\\n", "\n").replace("\r\n", "\n")

    def _parens(match: re.Match[str]) -> str:
        return match.group(0).replace("(", "#40;").replace(")", "#41;")

    lines = text.split("\n")
    head = lines[0].strip() if lines else ""
    if head.startswith(("graph ", "flowchart ")):
        text = _PAREN_IN_LABEL.sub(_parens, text)
        text = _SUBGRAPH_TITLE.sub(lambda m: f"subgraph {m.group(1)}[{m.group(2)}]", text)
    return text


def validate_mermaid(code: str) -> str:
    """Return '' when valid, else a short machine-readable error string."""
    text = (code or "").strip()
    if not text:
        return "empty diagram"
    if "\\n" in text and "\n" not in text:
        return "escaped newlines: payload needs unescaping, not reflection"
    first = text.splitlines()[0].strip()
    if not first.startswith(("graph ", "flowchart ", "sequenceDiagram", "classDiagram", "stateDiagram")):
        return f"bad header: {first[:60]!r}"
    if text.count("[") != text.count("]"):
        return "unbalanced square brackets"
    if text.count("(") != text.count(")"):
        return "unbalanced parentheses"
    if first.startswith(("graph ", "flowchart ")) and _PAREN_IN_LABEL.search(text):
        return "parentheses inside [] label break the flowchart parser"
    bad = _MERMAID_BAD.search(text)
    if bad:
        return f"illegal token near: {text[max(0, bad.start()-20):bad.end()+20]!r}"
    return ""


def _generate_node(generate: GenerateFn) -> Callable[[DiagramState], DiagramState]:
    def run(state: DiagramState) -> DiagramState:
        err = state.get("validation_error") or None
        code = generate(state["kind"], state["repo_name"], state["context"], err)
        history = list(state.get("history", [])) + [code]
        return {"mermaid": code, "attempts": state.get("attempts", 0) + 1, "history": history}

    return run


def _validate_node(state: DiagramState) -> DiagramState:
    return {"validation_error": validate_mermaid(state.get("mermaid", ""))}


def _route(state: DiagramState) -> str:
    if not state.get("validation_error") or state.get("attempts", 0) >= SETTINGS.mermaid_max_retries:
        return "done"
    return "reflect"


def _reflect_node(generate: GenerateFn) -> Callable[[DiagramState], DiagramState]:
    def run(state: DiagramState) -> DiagramState:
        return _generate_node(generate)(state)  # regenerate with validation_error in state

    return run


def run_eval_optimizer(
    kind: str, repo_name: str, context: str, generate: GenerateFn, first_draft: Optional[str] = None
) -> DiagramState:
    """Execute generate -> validate -> (reflect)? cycle; return terminal state."""
    try:
        from langgraph.graph import END, StateGraph
    except Exception:  # ponytail: LangGraph optional at runtime; linear fallback
        logger.warning("LangGraph unavailable; single-shot fallback")
        draft = first_draft if first_draft is not None else generate(kind, repo_name, context, None)
        return DiagramState(
            kind=kind,
            repo_name=repo_name,
            context=context,
            mermaid=draft,
            validation_error=validate_mermaid(draft),
            attempts=1,
            history=[draft],
        )

    graph = StateGraph(DiagramState)
    graph.add_node("generate", _generate_node(generate))
    graph.add_node("validate", _validate_node)
    graph.add_node("reflect", _reflect_node(generate))
    if first_draft is not None:
        graph.set_entry_point("validate")
    else:
        graph.set_entry_point("generate")
        graph.add_edge("generate", "validate")
    graph.add_conditional_edges("validate", _route, {"done": END, "reflect": "reflect"})
    graph.add_edge("reflect", "validate")
    app = graph.compile()
    initial: DiagramState = {
        "kind": kind,
        "repo_name": repo_name,
        "context": context,
        "mermaid": first_draft or "",
        "validation_error": "",
        "attempts": 0,
        "history": [],
    }
    final = app.invoke(initial)
    history_raw = final.get("history", [])
    return DiagramState(
        kind=str(final.get("kind", kind)),
        repo_name=str(final.get("repo_name", repo_name)),
        context=str(final.get("context", context)),
        mermaid=str(final.get("mermaid", "")),
        validation_error=str(final.get("validation_error", "")),
        attempts=int(final.get("attempts", 0)),
        history=[str(h) for h in history_raw] if isinstance(history_raw, list) else [],
    )
