"""Worker tests for status handling and analysis flow."""

import json
import os
import tempfile
from unittest.mock import Mock, patch

from worker import AnalysisWorker


def test_clean_json_response_handles_fences():
    worker = AnalysisWorker()
    raw = "```json\n{\"k\":\"v\"}\n```"
    assert worker._clean_json_response(raw) == '{"k":"v"}'


def test_parse_graph_data_returns_error_for_invalid_json():
    worker = AnalysisWorker()
    result = worker._parse_graph_data("{not-json}", "HLD")
    assert result["status"] == "error"


@patch("worker.DocumentationService")
@patch("worker.VectorStoreService")
@patch("worker.RepositoryService")
def test_run_analysis_success(mock_repo_cls, mock_vector_cls, mock_doc_cls):
    with tempfile.TemporaryDirectory() as temp_dir:
        status_file = os.path.join(temp_dir, "status.json")
        analysis_status_file = os.path.join(temp_dir, "status_1.json")

        repo_service = Mock()
        repo_service.build_collection_name.return_value = "example__repo"
        repo_service.collect_repository_files.return_value = {"app.py": "print('hello')"}
        mock_repo_cls.return_value = repo_service

        vector_service = Mock()
        vector_service.is_empty.return_value = True
        vector_service.query_similar_documents.return_value = "context"
        mock_vector_cls.return_value = vector_service

        doc_service = Mock()
        doc_service.generate_all_documentation.return_value = {
            "documentation": "# docs",
            "hld": '{"title":"HLD","description":"d","mermaid_code":"graph TD;A-->B"}',
            "lld": '{"title":"LLD","description":"d","mermaid_code":"sequenceDiagram\\nA->>B: hi"}',
            "flow": '{"title":"Flow","description":"d","mermaid_code":"flowchart LR\\nA-->B"}',
            "chat_summary": "summary",
        }
        doc_service.describe_backend.return_value = "local"
        mock_doc_cls.return_value = doc_service

        worker = AnalysisWorker()

        with patch("worker.config.STATUS_FILE_PATH", status_file), \
             patch("worker.config.LOCAL_CLONE_PATH", os.path.join(temp_dir, "repo")), \
             patch("worker.config.CHROMA_DB_PATH", os.path.join(temp_dir, "chroma")), \
             patch("worker.config.EMBEDDING_MODEL", "models/gemini-embedding-001"), \
             patch("worker.config.ALLOWED_EXTENSIONS", {".py"}), \
             patch("worker.config.IGNORED_DIRECTORIES", {".git"}), \
             patch.object(worker, "_update_database_log"), \
             patch.object(worker, "_save_to_history"):
            worker.status_file = status_file
            worker.run_analysis("https://github.com/example/repo", analysis_log_id=1)

        with open(analysis_status_file, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        assert data["status"] == "completed"
        assert data["stage"] == "completed"
        assert data["progress"] == 100
        assert "result" in data
        assert data["result"]["hld_graph"]["status"] == "ok"
        assert data["result"]["flow_graph"]["status"] == "ok"
        vector_service.reset.assert_called_once()


@patch("worker.DocumentationService")
@patch("worker.VectorStoreService")
@patch("worker.RepositoryService")
def test_run_analysis_refreshes_existing_index(mock_repo_cls, mock_vector_cls, mock_doc_cls):
    with tempfile.TemporaryDirectory() as temp_dir:
        status_file = os.path.join(temp_dir, "status.json")

        repo_service = Mock()
        repo_service.build_collection_name.return_value = "example__repo"
        repo_service.collect_repository_files.return_value = {"main.py": "print('fresh')"}
        mock_repo_cls.return_value = repo_service

        vector_service = Mock()
        vector_service.is_empty.return_value = False
        vector_service.query_similar_documents.return_value = "fresh context"
        mock_vector_cls.return_value = vector_service

        doc_service = Mock()
        doc_service.generate_all_documentation.return_value = {
            "documentation": "# fresh docs",
            "hld": '{"title":"HLD","description":"d","mermaid_code":"graph TD;A-->B"}',
            "lld": '{"title":"LLD","description":"d","mermaid_code":"sequenceDiagram\\nA->>B: hi"}',
            "flow": '{"title":"Flow","description":"d","mermaid_code":"flowchart LR\\nA-->B"}',
            "chat_summary": "fresh summary",
        }
        doc_service.describe_backend.return_value = "local"
        mock_doc_cls.return_value = doc_service

        worker = AnalysisWorker()

        with patch("worker.config.STATUS_FILE_PATH", status_file), \
             patch("worker.config.LOCAL_CLONE_PATH", os.path.join(temp_dir, "repo")), \
             patch("worker.config.CHROMA_DB_PATH", os.path.join(temp_dir, "chroma")), \
             patch("worker.config.EMBEDDING_MODEL", "models/gemini-embedding-001"), \
             patch("worker.config.ALLOWED_EXTENSIONS", {".py"}), \
             patch("worker.config.IGNORED_DIRECTORIES", {".git"}), \
             patch.object(worker, "_update_database_log"), \
             patch.object(worker, "_save_to_history"):
            worker.status_file = status_file
            worker.run_analysis("https://github.com/example/repo", analysis_log_id=2)

        repo_service.collect_repository_files.assert_called_once()
        vector_service.reset.assert_called_once()
        vector_service.generate_embeddings.assert_called_once_with({"main.py": "print('fresh')"})
