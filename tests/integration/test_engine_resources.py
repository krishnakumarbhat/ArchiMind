"""Integration: memory ceiling, concurrency guard, golden + blast endpoints."""
import json
import os
import resource
import tracemalloc

from app import AnalysisLog, create_app, db

FILES = {f"m{i}.py": f"class C{i}:\n    def run(self): return helper()\n" for i in range(30)}
FILES["main.py"] = "from m0 import C0\ndef main():\n    return C0().run()\n"


def _client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.app_context():
        db.create_all()
    return app.test_client()


def test_memory_ceiling_cpg_build():
    """CPG build over 31 files allocates little and grows RSS barely."""
    tracemalloc.start()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    from src.cpg._01_cpg_builder import build_graph, to_compact

    g = build_graph(FILES)
    assert g.number_of_nodes() > 60
    doc = to_compact(g)
    assert len(doc["edges"]) > 0
    current, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    # ponytail: ru_maxrss is process-wide (imports pollute it); assert the BUILD's growth
    growth_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - rss_before
    assert current < 50 * 1024 * 1024
    assert growth_kb < 150 * 1024, f"CPG build grew RSS by {growth_kb / 1024:.1f}MB"


def test_concurrency_guard_429_when_busy():
    """Second analysis while one runs is rejected with 429 + retry flag."""
    client = _client()
    with client.application.app_context():
        db.session.add(AnalysisLog(repo_url="https://github.com/a/b", status="processing", session_id="s1"))
        db.session.commit()
    resp = client.post("/api/analyze", json={"repo_url": "https://github.com/x/y"})
    assert resp.status_code == 429
    assert resp.get_json()["retry"] is True


def test_golden_endpoint_shape():
    """Golden endpoint serves descriptors even with an empty cache."""
    client = _client()
    resp = client.get("/api/golden")
    assert resp.status_code == 200
    assert len(resp.get_json()["golden"]) == 3


def test_blast_radius_needs_symbol_and_graph():
    """Missing symbol is 400; unknown graph is 404."""
    client = _client()
    assert client.get("/api/blast-radius").status_code == 400
    assert client.get("/api/blast-radius?symbol=X&golden=nope").status_code == 404


def test_blast_radius_over_golden_cache():
    """Golden blast-radius traces instantly when the cache is built."""
    from src.config._00_settings import SETTINGS
    from src.storage._00_sqlite_cache import CacheStore

    store = CacheStore(os.path.join(SETTINGS.data_path, "golden.db"))
    doc = store.get("golden:requests")
    if doc is None:
        raise AssertionError("golden cache not built; run scripts/build_golden_cache.py")
    client = _client()
    resp = client.get("/api/blast-radius?symbol=Session&golden=requests")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["symbol"] == "Session" and body["ms"] < 2000
    assert json.dumps(body)  # serializable
