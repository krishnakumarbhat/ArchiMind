"""Prompt guardrail: assistant scoped strictly to repository reasoning."""
from __future__ import annotations

import re

GUARDRAIL_MESSAGE = (
    "Guardrail Triggered: ArchiMind Assistant is scoped strictly to architectural "
    "reasoning and code inspection of this repository."
)

_OUT_OF_SCOPE = re.compile(
    r"\b(essay|homework|poem|recipe|horoscope|lottery|dating|politic|election|napoleon|"
    r"shakespeare|math homework|solve (this|my)|write (me |an essay|a poem)|who (won|is the president)|"
    r"stock (price|tip)|medical|diagnos|legal advice)\b",
    re.IGNORECASE,
)

_IN_SCOPE = re.compile(
    r"\b(architect\w*|diagrams?|mermaid|depend\w*|imports?|call ?graphs?|functions?|"
    r"class\w*|modules?|refactor\w*|dead ?code|blast|impacts?|break\w*|chang\w*|"
    r"invariants?|rules?|fails?|violat\w*|layers?|coupling|cohesion|flows?|trac\w*|"
    r"symbols?|repos?|codebase|tests?|coverage|challenge|explain|summar\w*|bullets?|"
    r"design\w*|structur\w*|patterns?)\b",
    re.IGNORECASE,
)


def check_scope(question: str) -> str:
    """Return '' when in scope, else the guardrail message (fail-closed on chit-chat)."""
    text = (question or "").strip()
    if not text:
        return GUARDRAIL_MESSAGE
    if _OUT_OF_SCOPE.search(text):
        return GUARDRAIL_MESSAGE
    if _IN_SCOPE.search(text):
        return ""
    # ponytail: unknown-and-short reads as chit-chat; unknown-and-long gets the model with repo context
    if len(text.split()) <= 6:
        return GUARDRAIL_MESSAGE
    return ""
