"""Service layer tests for current runtime behavior."""

import os
import tempfile
from unittest.mock import Mock, patch

os.environ.setdefault("GEMINI_API_KEY", "test-api-key")

from services import DocumentationService, VectorStoreService, _SimpleCollection


def test_simple_collection_add_and_query():
    with tempfile.TemporaryDirectory() as temp_dir:
        collection = _SimpleCollection(temp_dir, "repo")
        collection.add(
            embeddings=[[1.0, 0.0], [0.0, 1.0]],
            documents=["alpha", "beta"],
            ids=["a.py", "b.py"],
        )

        results = collection.query(query_embeddings=[[1.0, 0.0]], n_results=1)
        assert results["ids"][0][0] == "a.py"
        assert results["documents"][0][0] == "alpha"


@patch("services.genai.Client")
def test_vector_service_query_similar_documents(mock_client):
    VectorStoreService._instances.clear()

    mock_embed_response = Mock()
    mock_embed_response.embeddings = [Mock(values=[0.9, 0.1])]

    mock_genai_client = Mock()
    mock_genai_client.models.embed_content.return_value = mock_embed_response
    mock_client.return_value = mock_genai_client

    with tempfile.TemporaryDirectory() as temp_dir:
        service = VectorStoreService(temp_dir, "repo-name", "models/gemini-embedding-001")
        service.collection = _SimpleCollection(temp_dir, "repo_name")
        service.collection.add(
            embeddings=[[0.9, 0.1]],
            documents=["file content"],
            ids=["file.py"],
        )

        context = service.query_similar_documents("where is the code?", n_results=5)
        assert "file.py" in context
        assert "file content" in context


@patch("services.genai.Client")
def test_documentation_service_generate_all(mock_client):
    mock_response = Mock()
    mock_response.text = "generated"

    mock_genai_client = Mock()
    mock_genai_client.models.generate_content.return_value = mock_response
    mock_client.return_value = mock_genai_client

    service = DocumentationService(api_key="fake-key", model_name="gemini-2.5-pro")
    data = service.generate_all_documentation("context", "repo")

    assert set(data.keys()) == {"documentation", "hld", "lld", "chat_summary"}
    assert all(value == "generated" for value in data.values())
