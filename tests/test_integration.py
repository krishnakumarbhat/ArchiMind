"""Light integration tests for current ArchiMind runtime."""

import os
from unittest.mock import patch

os.environ.setdefault("GEMINI_API_KEY", "test-api-key")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///data/test_integration.db")

from app import create_app


def test_analyze_endpoint_starts_worker_process():
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    with patch("subprocess.Popen") as mock_popen:
        response = client.post(
            "/api/analyze",
            json={"repo_url": "https://github.com/example/repo"},
        )

    assert response.status_code == 202
    payload = response.get_json()
    assert payload["status"] == "success"
    assert mock_popen.called
