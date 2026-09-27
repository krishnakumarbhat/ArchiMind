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
    r"\b(architect|diagram|mermaid|dependen|import|call ?graph|function|class|module|"
    r"refactor|dead ?code|blast|impact|invariant|layer|coupling|cohesion|flow|trace|"
    r"symbol|repo|codebase|test|coverage|challenge|explain (this|the) (code|function|class|file))\b",
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
