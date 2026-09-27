"""Seed-data loader for 1-click golden demos."""
import logging
from typing import Any, Dict, List

from src.config._01_constants import GOLDEN_REPOS
from src.storage._00_sqlite_cache import CacheStore

logger = logging.getLogger(__name__)


def golden_key(repo_id: str) -> str:
    """Cache key for a golden repository artifact."""
    return f"golden:{repo_id}"


GOLDEN_DISPLAY = {
    "flask": ("Flask Core", "Web framework engine"),
    "requests": ("Requests HTTP", "Distributed client architecture"),
    "sqlmodel": ("SQLModel", "Data models & ORM layer"),
}


def list_golden(store: CacheStore) -> List[Dict[str, Any]]:
    """Return cached golden artifacts with fallback descriptors when unbuilt."""
    out: List[Dict[str, Any]] = []
    for repo_id, url, desc in GOLDEN_REPOS:
        title, subtitle = GOLDEN_DISPLAY.get(repo_id, (repo_id, desc))
        doc = store.get(golden_key(repo_id))
        if doc is None:
            out.append(
                {
                    "id": repo_id, "title": title, "subtitle": subtitle,
                    "repo_url": url, "description": desc, "cached": False,
                }
            )
        else:
            doc = dict(doc)
            doc["cached"] = True
            doc.setdefault("title", title)
            doc.setdefault("subtitle", subtitle)
            out.append(doc)
    return out
