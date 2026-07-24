"""Flask app tests for current route behavior."""

import os
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///data/test_app.db")

from app import AnalysisLog, User, create_app, db


def _make_client():
    app = create_app()
    app.config["TESTING"] = True
    with app.app_context():
        db.drop_all()
        db.create_all()
    return app, app.test_client()


def test_index_route_returns_200():
    _, client = _make_client()
    response = client.get("/")
    assert response.status_code == 200


def test_api_analyze_requires_repo_url():
    _, client = _make_client()
    response = client.post("/api/analyze", json={})
    assert response.status_code == 400
    assert "error" in response.get_json()


@patch("app.RepositoryService.get_repository_preview")
def test_api_preview_returns_repository_metadata(mock_preview):
    mock_preview.return_value = {
        "full_name": "example/repo",
        "description": "Previewed repository",
        "language": "Python",
        "stars": 42,
        "updated_at": "2026-03-31T00:00:00Z",
        "html_url": "https://github.com/example/repo",
        "topics": ["ai", "docs"],
    }

    _, client = _make_client()
    response = client.get("/api/preview", query_string={"repo_url": "https://github.com/example/repo"})

    assert response.status_code == 200
    assert response.get_json()["full_name"] == "example/repo"


@patch("app.DocumentationService")
@patch("app.VectorStoreService")
def test_api_chat_returns_grounded_answer(mock_vector_cls, mock_doc_cls):
    vector_service = mock_vector_cls.return_value
    vector_service.is_empty.return_value = False
    vector_service.query_similar_documents.return_value = "--- File: app.py ---\n\ndef create_app(): pass"

    doc_service = mock_doc_cls.return_value
    doc_service.generate_chat_answer.return_value = "The app factory creates the Flask application."
    doc_service.describe_backend.return_value = "local"

    _, client = _make_client()
    response = client.post(
        "/api/chat",
        json={
            "repo_url": "https://github.com/example/repo",
            "repo_name": "repo",
            "question": "How is the app created?",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["answer"] == "The app factory creates the Flask application."
    assert payload["backend"] == "local"
    assert mock_vector_cls.call_args.kwargs["collection_name"] == "example__repo"


@patch("subprocess.Popen")
def test_api_analyze_success(mock_popen):
    app, client = _make_client()
    response = client.post("/api/analyze", json={"repo_url": "https://github.com/example/repo"})
    assert response.status_code == 202
    assert response.get_json()["status"] == "success"

    with app.app_context():
        assert AnalysisLog.query.count() == 1
    assert mock_popen.called


def test_api_check_limit_anonymous_structure():
    _, client = _make_client()
    response = client.get("/api/check-limit")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["authenticated"] is False
    assert "can_generate" in payload
    assert "count" in payload
    assert "limit" in payload


def test_user_model_analysis_count():
    app, _ = _make_client()
    with app.app_context():
        user = User(email="test@example.com", first_name="Test", password="hashed")
        db.session.add(user)
        db.session.commit()

        for index in range(2):
            db.session.add(
                AnalysisLog(
                    user_id=user.id,
                    repo_url=f"https://github.com/example/repo-{index}",
                    status="completed",
                )
            )
        db.session.commit()

        refreshed = db.session.get(User, user.id)
        assert refreshed.get_analysis_count() == 2
