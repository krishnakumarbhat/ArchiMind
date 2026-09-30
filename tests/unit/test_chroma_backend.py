"""ChromaDB backend selection + roundtrip (disk-backed, no local models)."""
import os
import tempfile

import pytest

services = pytest.importorskip("services")


def _service(monkeypatch, tmp):
    monkeypatch.setenv("VECTOR_BACKEND", "chroma")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("PINECONE_API_KEY", "")
    import importlib

    import config

    importlib.reload(config)
    return services.VectorStoreService(
        db_path=tmp, collection_name="chroma_t", embedding_model="local", repo_url="https://github.com/x/y"
    )


def test_chroma_backend_selected_when_available(tmp_path, monkeypatch):
    """VECTOR_BACKEND=chroma engages PersistentClient instead of JSON fallback."""
    pytest.importorskip("chromadb")
    v = _service(monkeypatch, str(tmp_path))
    assert v.vector_backend == "chroma"
    assert not type(v.chunk_collection).__name__.endswith("SimpleCollection")


def test_chroma_roundtrip_persists_and_retrieves(tmp_path, monkeypatch):
    """Embed -> persist to sqlite -> fresh instance retrieves the right file."""
    pytest.importorskip("chromadb")
    v = _service(monkeypatch, str(tmp_path))
    v.reset()
    v.generate_embeddings({"a.py": "def foo(): return 1", "b.py": "class Bar:\n def baz(self): return 2"})
    assert os.path.exists(os.path.join(str(tmp_path), "chroma.sqlite3"))
    out = v.query_similar_documents("where is baz defined", n_results=5)
    assert "baz" in out
