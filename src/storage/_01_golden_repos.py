"""Bundled golden demos: instant, compute-free workspace fixtures."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

from src.config._01_constants import GOLDEN_REPOS

logger = logging.getLogger(__name__)

FIXTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_fixtures")


def golden_key(repo_id: str) -> str:
    """Cache key for a golden repository artifact."""
    return f"golden:{repo_id}"


@lru_cache(maxsize=8)
def load_golden(repo_id: str) -> Optional[Dict[str, Any]]:
    """Full fixture (incl. CPG artifact) or None; cached in-process after first read."""
    if not repo_id.isidentifier():
        return None  # blocks path traversal via the id
    path = os.path.join(FIXTURE_DIR, f"{repo_id}.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        return doc if isinstance(doc, dict) else None
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("Golden fixture %s unavailable: %s", repo_id, exc)
        return None


def public_view(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Fixture minus the heavy CPG artifact (served to browsers)."""
    return {k: v for k, v in doc.items() if k != "cpg_artifact"}


def list_golden(_store: Any = None) -> List[Dict[str, Any]]:
    """Light card list for the landing page."""
    out: List[Dict[str, Any]] = []
    for repo_id, title, subtitle, repo, _dirs in GOLDEN_REPOS:
        doc = load_golden(repo_id)
        out.append(
            {
                "id": repo_id,
                "title": title,
                "subtitle": subtitle,
                "repo_url": f"https://github.com/{repo}",
                "cached": doc is not None,
                "stats": (doc or {}).get("stats", {}),
            }
        )
    return out
