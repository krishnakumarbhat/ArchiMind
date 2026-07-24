"""Service layer tests for local-first runtime behavior."""

import json
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

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


def test_vector_service_reloads_updated_collection_from_disk():
    with tempfile.TemporaryDirectory() as temp_dir:
        service = VectorStoreService(temp_dir, "repo-name", "local", repo_url="https://github.com/example/repo")
        service.generate_embeddings(
            {
                "app.py": "def alpha_feature():\n    return True\n",
            }
        )

        stale_context = service.query_similar_documents("alpha feature", n_results=2)
        assert "alpha_feature" in stale_context

        summary_collection = _SimpleCollection(temp_dir, "repo_name_summaries")
        chunk_collection = _SimpleCollection(temp_dir, "repo_name_chunks")
        summary_collection.clear()
        chunk_collection.clear()

        summary_doc = "auth.py appears to define core logic around: def beta_feature():. It contains approximately 0 classes, 1 functions, and 0 import statements."
        summary_collection.add(
            documents=[summary_doc],
            ids=["beta-summary"],
            metadatas=[
                {
                    "file_path": "auth.py",
                    "language": "python",
                    "function_name": "",
                    "github_url": "https://github.com/example/repo/blob/main/auth.py",
                }
            ],
            embeddings=[service._embed_texts([summary_doc])[0]],
        )
        chunk_doc = "def beta_feature():\n    return True\n"
        chunk_collection.add(
            documents=[chunk_doc],
            ids=["beta-chunk"],
            metadatas=[
                {
                    "file_path": "auth.py",
                    "language": "python",
                    "function_name": "beta_feature",
                    "github_url": "https://github.com/example/repo/blob/main/auth.py#L1-L2",
                    "start_line": 1,
                    "end_line": 2,
                }
            ],
            embeddings=[service._embed_texts([chunk_doc])[0]],
        )

        reloaded_service = VectorStoreService(temp_dir, "repo-name", "local", repo_url="https://github.com/example/repo")
        fresh_context = reloaded_service.query_similar_documents("beta feature", n_results=2)

        assert "beta_feature" in fresh_context
        assert "alpha_feature" not in fresh_context


def test_documentation_service_generate_all():
    service = DocumentationService(model_name="local")
    data = service.generate_all_documentation("--- File: app.py ---\n\ndef f(): pass", "repo")

    assert set(data.keys()) == {"documentation", "hld", "lld", "flow", "chat_summary"}
    assert data["documentation"]
    assert data["hld"]
    assert data["lld"]
    assert data["flow"]
    assert data["chat_summary"]


def test_documentation_service_fallback_stays_repo_grounded():
    context = (
        "--- File: README.md ---\n"
        "language=markdown\n"
        "function_name=\n"
        "github_url=https://github.com/example/RNAtoDNA/blob/main/README.md\n\n"
        "# RNAtoDNA\n\n"
        "RNAtoDNA is a Flask application for converting RNA sequences into DNA sequences.\n\n"
        "--- File: app.py ---\n"
        "language=python\n"
        "function_name=home\n"
        "github_url=https://github.com/example/RNAtoDNA/blob/main/app.py\n\n"
        "from flask import Flask, render_template, request\n\n"
        "app = Flask(__name__)\n\n"
        "@app.route('/')\n"
        "def home():\n"
        "    return render_template('index.html')\n"
    )

    service = DocumentationService(model_name="local")
    data = service.generate_all_documentation(context, "RNAtoDNA")
    flow = json.loads(data["flow"])

    assert "LangGraph" not in data["documentation"]
    assert "LangGraph" not in data["chat_summary"]
    assert "Flask" in data["documentation"]
    assert "app.py" in data["documentation"]
    assert flow["mermaid_code"].startswith("flowchart")


def test_documentation_service_uses_gemini_generate_content_with_high_thinking():
    mock_client = Mock()
    mock_client.models.generate_content.side_effect = [
        SimpleNamespace(text="# Architecture Handbook"),
        SimpleNamespace(text='{"title":"HLD","description":"overview","mermaid_code":"flowchart TD\\nA-->B"}'),
        SimpleNamespace(text='{"title":"LLD","description":"details","mermaid_code":"sequenceDiagram\\nA->>B: hi"}'),
        SimpleNamespace(text='{"title":"Flow","description":"path","mermaid_code":"flowchart LR\\nA-->B"}'),
        SimpleNamespace(text="Short onboarding summary"),
    ]

    mock_genai = Mock()
    mock_genai.Client.return_value = MagicMock()
    mock_genai.Client.return_value.__enter__.return_value = mock_client

    mock_types = Mock()
    mock_types.ThinkingConfig.side_effect = lambda **kwargs: {"thinking_level": kwargs["thinking_level"]}
    mock_types.GenerateContentConfig.side_effect = lambda **kwargs: kwargs
    mock_types.HttpOptions.side_effect = lambda **kwargs: kwargs

    with patch("services.genai", mock_genai), patch("services.genai_types", mock_types):
        service = DocumentationService(
            api_key="test-api-key",
            model_name="gemini-3.1-flash-lite-preview",
            chat_model_name="gemini-3.1-flash-lite-preview",
            thinking_level="high",
        )
        data = service.generate_all_documentation("--- File: app.py ---\n\ndef f(): pass", "repo")

    assert data["documentation"] == "# Architecture Handbook"
    assert data["chat_summary"] == "Short onboarding summary"
    assert service.describe_backend() == "gemini:gemini-3.1-flash-lite-preview"
    assert mock_client.models.generate_content.call_count == 5

    first_call = mock_client.models.generate_content.call_args_list[0].kwargs
    assert first_call["model"] == "gemini-3.1-flash-lite-preview"
    assert first_call["config"]["thinking_config"] == {"thinking_level": "high"}


def test_documentation_service_generate_chat_answer_uses_gemini_with_question_and_context():
    mock_client = Mock()
    mock_client.models.generate_content.return_value = SimpleNamespace(text="Grounded answer")

    mock_genai = Mock()
    mock_genai.Client.return_value = MagicMock()
    mock_genai.Client.return_value.__enter__.return_value = mock_client

    mock_types = Mock()
    mock_types.ThinkingConfig.side_effect = lambda **kwargs: {"thinking_level": kwargs["thinking_level"]}
    mock_types.GenerateContentConfig.side_effect = lambda **kwargs: kwargs
    mock_types.HttpOptions.side_effect = lambda **kwargs: kwargs

    with patch("services.genai", mock_genai), patch("services.genai_types", mock_types):
        service = DocumentationService(
            api_key="test-api-key",
            model_name="gemini-3.1-flash-lite-preview",
            chat_model_name="gemini-3.1-flash-lite-preview",
            thinking_level="high",
        )
        answer = service.generate_chat_answer(
            "--- File: app.py ---\nlanguage=python\nfunction_name=create_app\ngithub_url=https://github.com/example/repo/blob/main/app.py#L1-L3\n\ndef create_app():\n    return app\n",
            "repo",
            "How is the app created?",
        )

    assert answer == "Grounded answer"
    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert "How is the app created?" in call_kwargs["contents"]
    assert "create_app" in call_kwargs["contents"]


def test_documentation_service_generate_chat_answer_local_fallback_is_direct():
    context = (
        "--- File: README.md ---\n"
        "language=markdown\n"
        "function_name=\n"
        "github_url=https://github.com/example/RNAtoDNA/blob/main/README.md\n\n"
        "# RNAtoDNA\n\n"
        "RNAtoDNA is a Flask application for converting RNA sequences into DNA sequences.\n\n"
        "--- File: main.py ---\n"
        "language=python\n"
        "function_name=\n"
        "github_url=https://github.com/example/RNAtoDNA/blob/main/main.py\n\n"
        "from website import create_app\n"
        "from flask import Flask\n\n"
        "app = create_app()\n"
    )

    service = DocumentationService(model_name="local")
    answer = service.generate_chat_answer(
        context,
        "RNAtoDNA",
        "What is the main entry point and what framework does this repo use?",
    )

    assert "Direct answer:" in answer
    assert "main.py" in answer
    assert "Flask" in answer


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
