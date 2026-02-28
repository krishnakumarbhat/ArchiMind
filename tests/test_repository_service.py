"""Repository service tests aligned with current implementation."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from services import RepositoryService


def test_clone_repository_returns_true_if_path_exists():
    service = RepositoryService()
    with tempfile.TemporaryDirectory() as temp_dir:
        assert service.clone_repository("https://github.com/example/repo", temp_dir) is True


@patch("git.Repo.clone_from")
def test_clone_repository_calls_git_clone(mock_clone):
    service = RepositoryService()
    with tempfile.TemporaryDirectory() as temp_dir:
        target = os.path.join(temp_dir, "repo")
        assert service.clone_repository("https://github.com/example/repo", target) is True
        mock_clone.assert_called_once()


def test_read_repository_files_filters_extensions_and_ignored_dirs():
    service = RepositoryService()
    with tempfile.TemporaryDirectory() as temp_dir:
        Path(temp_dir, "main.py").write_text("print('ok')", encoding="utf-8")
        Path(temp_dir, "README.md").write_text("# hello", encoding="utf-8")
        ignored = Path(temp_dir, "node_modules")
        ignored.mkdir(parents=True, exist_ok=True)
        Path(ignored, "bad.js").write_text("ignored", encoding="utf-8")

        result = service.read_repository_files(
            repo_path=temp_dir,
            allowed_extensions={".py", ".md"},
            ignored_dirs={"node_modules", ".git"},
        )

        assert "main.py" in result
        assert "README.md" in result
        assert all("node_modules" not in path for path in result.keys())
