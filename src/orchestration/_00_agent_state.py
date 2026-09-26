"""TypedDict state for the LangGraph evaluator-optimizer cycle."""
from typing import List, TypedDict


class DiagramState(TypedDict, total=False):
    """State carried around the generate -> validate -> reflect loop."""

    kind: str  # hld | lld | flow
    repo_name: str
    context: str
    mermaid: str
    validation_error: str
    attempts: int
    history: List[str]
