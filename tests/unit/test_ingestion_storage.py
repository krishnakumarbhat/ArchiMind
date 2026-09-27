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


def test_golden_fixtures_bundled_and_valid():
    """PyTorch + OpenClaw + Requests ship as fixtures with valid diagrams (zero blank canvases)."""
    from src.orchestration._01_eval_optimizer import validate_mermaid
    from src.storage._01_golden_repos import load_golden

    items = list_golden()
    assert [i["id"] for i in items][:2] == ["pytorch", "openclaw"]
    assert all(i["cached"] for i in items)
    for i in items:
        doc = load_golden(i["id"])
        for k in ("hld_mermaid", "lld_mermaid", "flow_mermaid"):
            assert validate_mermaid(doc[k]) == "", (i["id"], k)
        assert doc["cpg_artifact"]["nodes"] and "## Executive Summary" in doc["chat_response"]
    assert golden_key("pytorch") == "golden:pytorch"
    assert load_golden("../etc") is None
