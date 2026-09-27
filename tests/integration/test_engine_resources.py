"""Integration: memory ceiling, concurrency guard, golden + blast endpoints."""
import json
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
    """Golden list is light (no graph payload) and detail omits the raw CPG."""
    client = _client()
    items = client.get("/api/golden").get_json()["golden"]
    assert [i["id"] for i in items][:2] == ["pytorch", "openclaw"]
    detail = client.get("/api/golden/pytorch").get_json()
    assert "hld_mermaid" in detail and "cpg_artifact" not in detail
    assert client.get("/api/golden/nope").status_code == 404


def test_blast_radius_needs_symbol_and_graph():
    """Missing symbol is 400; unknown graph is 404."""
    client = _client()
    assert client.get("/api/blast-radius").status_code == 400
    assert client.get("/api/blast-radius?symbol=X&golden=nope").status_code == 404


def test_blast_radius_over_golden_fixture():
    """Golden blast-radius traces from the bundled fixture well under budget."""
    client = _client()
    body = client.get("/api/blast-radius?symbol=Module&golden=pytorch").get_json()
    assert body["symbol"] == "Module" and body["edges"] > 0 and body["ms"] < 2000
    assert json.dumps(body)
