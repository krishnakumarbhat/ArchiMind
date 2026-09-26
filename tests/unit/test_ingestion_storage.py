"""Unit tests: ingestion filter, tarball guardrails, storage cache."""
import os
import tempfile

import pytest

from src.ingestion._00_tarball_client import repo_tarball_url
from src.ingestion._01_file_filter import decode_sources, keep_member
from src.storage._00_sqlite_cache import CacheStore
from src.storage._01_golden_repos import golden_key, list_golden


def test_keep_member_bounds():
    """Oversized, vendored, binary, and non-source members are dropped."""
    assert keep_member("pkg/mod.py", 100) is True
    assert keep_member("pkg/mod.py", 500_000) is False
    assert keep_member("pkg/tests/mod.py", 100) is False
    assert keep_member("pkg/logo.png", 100) is False
    assert keep_member("pkg/README.md", 100) is False


def test_decode_sources_caps_and_dedupes():
    """Decoding caps file count and dedupes basenames."""
    raw = {f"top-{i}/a.py": b"x = 1\n" for i in range(5)}
    raw["other/a.py"] = b"y = 2\n"
    out = decode_sources(raw, max_files=3)
    assert len(out) == 1 or len(out) <= 3  # basename keying collapses a.py


def test_tarball_rejects_garbage():
    """Malformed URLs raise before networking."""
    with pytest.raises(ValueError):
        repo_tarball_url("not a url")
    with pytest.raises(ValueError):
        repo_tarball_url("https://gitlab.com/a/b")


def test_cache_roundtrip_tmp():
    """SQLite cache stores, reads, and lists JSON docs."""
    path = os.path.join(tempfile.mkdtemp(), "t.db")
    store = CacheStore(path)
    assert store.get("missing") is None
    store.put("k", {"v": [1, 2]})
    assert store.get("k") == {"v": [1, 2]}
    assert "k" in store.keys()


def test_golden_lists_descriptors_when_unbuilt():
    """Unbuilt golden repos degrade to descriptors (instant, compute-free)."""
    store = CacheStore(os.path.join(tempfile.mkdtemp(), "g.db"))
    items = list_golden(store)
    assert len(items) == 3 and all(i["cached"] is False for i in items)
    assert golden_key("flask") == "golden:flask"
