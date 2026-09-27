"""Model fingerprint scrubber + engine branding."""
from __future__ import annotations

import re

ENGINE_LABEL = "ArchiMind Neural Graph Core"
ENGINE_SHORT = "ArchiMind v2 CPG Harness"

_FINGERPRINTS = re.compile(
    r"gemini[-\w.]*|google-genai|generativelanguage|text-embedding-\d+|gpt-[\w.]*|"
    r"claude[\w.-]*|llama[\w.-]*",
    re.IGNORECASE,
)
_BACKEND_TAG = re.compile(r"Backend:\s*\S+", re.IGNORECASE)


def scrub(text: object) -> str:
    """Replace provider/model mentions with the ArchiMind engine label."""
    out = _BACKEND_TAG.sub("Engine: " + ENGINE_LABEL, str(text or ""))
    return _FINGERPRINTS.sub(ENGINE_LABEL, out)


def engine_label() -> str:
    """Public engine indicator for UI and API responses."""
    return ENGINE_LABEL
