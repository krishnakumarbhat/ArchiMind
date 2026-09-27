"""Fetch a bounded subtree of a huge repo via the contents API (no clone, no full tarball).

Needed for monorepos like pytorch/pytorch (GBs) where even a shallow tarball
blows the 60MB ingest cap: list chosen directories, then stream individual
raw files, capped per directory and in total.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import Dict, Iterable

from src.ingestion._01_file_filter import keep_member

logger = logging.getLogger(__name__)


def _get(url: str, timeout: int = 30) -> bytes:
    headers = {"User-Agent": "archimind-engine", "Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN", "")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data: bytes = resp.read()
        return data


def fetch_subtree(repo: str, dirs: Iterable[str], per_dir: int = 30, total: int = 80) -> Dict[str, str]:
    """Return {path: source} for up to `total` source files under `dirs` of owner/repo."""
    out: Dict[str, str] = {}
    for d in dirs:
        listing = json.loads(_get(f"https://api.github.com/repos/{repo}/contents/{d}"))
        if not isinstance(listing, list):
            logger.warning("Subtree %s/%s unavailable: %s", repo, d, listing)
            continue
        taken = 0
        for item in listing:
            if len(out) >= total or taken >= per_dir:
                break
            name, size = str(item.get("name", "")), int(item.get("size") or 0)
            if item.get("type") != "file" or any(t in name for t in (".test", ".spec", "test-support", "test-utils")) or name.endswith(".d.ts"):
                continue
            if not keep_member(item["path"], size):
                continue
            try:
                out[item["path"]] = _get(item["download_url"]).decode("utf-8", "replace")
                taken += 1
            except Exception as exc:
                logger.warning("Skip %s: %s", item["path"], exc)
    logger.info("Subtree %s: %d files from %s", repo, len(out), list(dirs))
    return out
