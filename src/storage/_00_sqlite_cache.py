"""Lightweight SQLite JSON/artifact store (pre-computed analyses)."""
import json
import logging
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CacheStore:
    """Single-file SQLite cache: key -> JSON doc + timestamp."""

    def __init__(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.path = path
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS cache (k TEXT PRIMARY KEY, v TEXT, ts INTEGER)")

    def put(self, key: str, doc: Dict[str, Any]) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache VALUES (?, ?, ?)", (key, json.dumps(doc), int(time.time()))
            )

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT v FROM cache WHERE k = ?", (key,)).fetchone()
        if not row:
            return None
        try:
            loaded = json.loads(row[0])
            return loaded if isinstance(loaded, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None

    def keys(self) -> List[str]:
        with sqlite3.connect(self.path) as conn:
            return [r[0] for r in conn.execute("SELECT k FROM cache")]
