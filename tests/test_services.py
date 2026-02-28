"""Service layer tests for local-first runtime behavior."""

import tempfile

from services import DocumentationService, VectorStoreService, _SimpleCollection
from services import RepositoryService


def test_simple_collection_add_and_query():
    with tempfile.TemporaryDirectory() as temp_dir:
        collection = _SimpleCollection(temp_dir, "repo")
        collection.add(
            documents=["alpha function"],
            ids=["a.py"],
            metadatas=[{"file_path": "a.py"}],
        )

        results = collection.query(query_texts=["alpha"], n_results=1)
        assert results["ids"][0][0] == "a.py"
        assert "alpha" in results["documents"][0][0]


def test_vector_service_query_similar_documents():
    VectorStoreService._instances.clear()

    with tempfile.TemporaryDirectory() as temp_dir:
        service = VectorStoreService(temp_dir, "repo-name", "local", repo_url="https://github.com/example/repo")
        service.summary_collection = _SimpleCollection(temp_dir, "repo_name_summaries")
        service.chunk_collection = _SimpleCollection(temp_dir, "repo_name_chunks")

        service.generate_embeddings(
            {
                "app.py": "def verify_token(token):\n    return token is not None\n",
                "auth.py": "class AuthService:\n    def login(self):\n        return True\n",
            }
        )

        context = service.query_similar_documents("how does auth work?", n_results=3)
        assert "File:" in context
        assert "file_path=" not in context
        assert "github_url=" in context


def test_documentation_service_generate_all():
    service = DocumentationService(model_name="local")
    data = service.generate_all_documentation("--- File: app.py ---\n\ndef f(): pass", "repo")

    assert set(data.keys()) == {"documentation", "hld", "lld", "chat_summary"}
    assert data["documentation"]
    assert data["hld"]
    assert data["lld"]
    assert data["chat_summary"]


def test_repository_service_parse_github_url():
    service = RepositoryService()
    assert service._parse_github_repo("https://github.com/opendilab/LightZero") == ("opendilab", "LightZero")
    assert service._parse_github_repo("git@github.com:opendilab/LightZero.git") == ("opendilab", "LightZero")


def test_repository_service_select_remote_paths_prioritizes_core_files():
    service = RepositoryService()
    tree_entries = [
        {"type": "blob", "path": "README.md", "size": 4000},
        {"type": "blob", "path": "docs/architecture.md", "size": 12000},
        {"type": "blob", "path": "src/service/auth.py", "size": 9000},
        {"type": "blob", "path": "assets/image.png", "size": 1000},
    ]
    selected = service._select_remote_paths(tree_entries, {".py", ".md"}, {".git", "node_modules"})
    selected_paths = [entry["path"] for entry in selected]
    assert "README.md" in selected_paths
    assert "docs/architecture.md" in selected_paths
    assert "src/service/auth.py" in selected_paths
    assert "assets/image.png" not in selected_paths
