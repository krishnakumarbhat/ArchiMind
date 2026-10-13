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


class MermaidEvaluatorOptimizer:
    """Self-healing Mermaid synthesis loop with grammar validation."""

    _BAD = re.compile(r"```|<script|\{\{|\}\}|\[\[|\]\]|#(?!\d+;|[0-9a-fA-F]{3,8}\b)")
    _PAREN_IN_LABEL = re.compile(r"\[[^\[\]\n]*[()][^\[\]\n]*\]")
    _SUBGRAPH_TITLE = re.compile(r"(?m)^\s*subgraph\s+([A-Za-z0-9_]+)\s+\[([^\]]+)\]")

    def __init__(self, max_retries: int = SETTINGS.mermaid_max_retries) -> None:
        """Create the loop with a reflection-attempt cap."""
        self._max_retries = max_retries

    @classmethod
    def normalize(cls, code: str) -> str:
        """Make LLM output parseable: unescape newlines, quote subgraph titles, entity-encode label parens."""
        text = (code or "").replace("\\r\n", "\n").replace("\\n", "\n").replace("\r\n", "\n")

        def _parens(match: re.Match[str]) -> str:
            return match.group(0).replace("(", "#40;").replace(")", "#41;")

        lines = text.split("\n")
        head = lines[0].strip() if lines else ""
        if head.startswith(("graph ", "flowchart ")):
            text = cls._PAREN_IN_LABEL.sub(_parens, text)
            text = cls._SUBGRAPH_TITLE.sub(lambda m: f"subgraph {m.group(1)}[{m.group(2)}]", text)
        return text

    @classmethod
    def validate(cls, code: str) -> str:
        """Return '' when renderable, else a machine-readable error string."""
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
        if first.startswith(("graph ", "flowchart ")) and cls._PAREN_IN_LABEL.search(text):
            return "parentheses inside [] label break the flowchart parser"
        bad = cls._BAD.search(text)
        if bad:
            return f"illegal token near: {text[max(0, bad.start()-20):bad.end()+20]!r}"
        return ""

    @staticmethod
    def _generate_node(generate: GenerateFn) -> Callable[[DiagramState], DiagramState]:
        """Build the LangGraph node that drafts one diagram version."""

        def run(state: DiagramState) -> DiagramState:
            err = state.get("validation_error") or None
            code = generate(
                str(state.get("kind", "")),
                str(state.get("repo_name", "")),
                str(state.get("context", "")),
                err,
            )
            history = list(state.get("history", [])) + [code]
            return {"mermaid": code, "attempts": int(state.get("attempts", 0) or 0) + 1, "history": history}

        return run

    @classmethod
    def _validate_node(cls, state: DiagramState) -> DiagramState:
        """Build the LangGraph node that grammar-checks the draft."""
        return {"validation_error": cls.validate(state.get("mermaid", ""))}

    def _route(self, state: DiagramState) -> str:
        """Route to reflection while errors remain and retries are left."""
        if not state.get("validation_error") or state.get("attempts", 0) >= self._max_retries:
            return "done"
        return "reflect"

    @staticmethod
    def _reflect_node(generate: GenerateFn) -> Callable[[DiagramState], DiagramState]:
        """Build the LangGraph node that regenerates with the error attached."""

        def run(state: DiagramState) -> DiagramState:
            return MermaidEvaluatorOptimizer._generate_node(generate)(state)

        return run

    def _terminal(self, fields: Dict[str, object]) -> DiagramState:
        """Pack raw graph output into a typed terminal state."""
        history = fields.get("history", [])
        get = fields.get
        attempts_raw = get("attempts", 0)
        attempts = attempts_raw if isinstance(attempts_raw, int) else 0
        return DiagramState(
            kind=str(get("kind", "")),
            repo_name=str(get("repo_name", "")),
            context=str(get("context", "")),
            mermaid=str(get("mermaid", "")),
            validation_error=str(get("validation_error", "")),
            attempts=attempts,
            history=[str(h) for h in history] if isinstance(history, list) else [],
        )

    def run(
        self, kind: str, repo_name: str, context: str, generate: GenerateFn, first_draft: Optional[str] = None
    ) -> DiagramState:
        """Execute generate -> validate -> (reflect)? and return the terminal state."""
        try:
            from langgraph.graph import END, StateGraph
        except Exception:  # ponytail: LangGraph optional at runtime; linear fallback
            logger.warning("LangGraph unavailable; single-shot fallback")
            draft = first_draft if first_draft is not None else generate(kind, repo_name, context, None)
            return self._terminal(
                {
                    "kind": kind,
                    "repo_name": repo_name,
                    "context": context,
                    "mermaid": draft,
                    "validation_error": self.validate(draft),
                    "attempts": 1,
                    "history": [draft],
                }
            )
        graph = StateGraph(DiagramState)
        graph.add_node("generate", self._generate_node(generate))
        graph.add_node("validate", self._validate_node)
        graph.add_node("reflect", self._reflect_node(generate))
        if first_draft is not None:
            graph.set_entry_point("validate")
        else:
            graph.set_entry_point("generate")
            graph.add_edge("generate", "validate")
        graph.add_conditional_edges("validate", self._route, {"done": END, "reflect": "reflect"})
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
        return self._terminal(dict(app.invoke(initial)))
