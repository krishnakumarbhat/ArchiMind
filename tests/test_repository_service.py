"""Repository service tests aligned with current implementation."""

import os
import tempfile
from http.client import IncompleteRead
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


class _PartialReadResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *_args, **_kwargs):
        raise IncompleteRead(b"partial payload", 64)


@patch("services.urlopen", return_value=_PartialReadResponse())
def test_http_get_text_uses_partial_payload_when_remote_read_is_interrupted(_mock_urlopen):
    service = RepositoryService()
    text = service._http_get_text("https://example.com/repo.txt")
    assert text == "partial payload"


class _JsonResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *_args, **_kwargs):
        return self.payload


@patch("services.time.sleep", return_value=None)
@patch(
    "services.urlopen",
    side_effect=[
        _PartialReadResponse(),
        _JsonResponse(b'{"full_name": "example/repo"}'),
    ],
)
def test_http_get_json_retries_after_incomplete_partial_json(_mock_urlopen, _mock_sleep):
    service = RepositoryService()
    payload = service._http_get_json("https://api.github.com/repos/example/repo")
    assert payload == {"full_name": "example/repo"}


def test_build_collection_name_uses_owner_and_repo_slug():
    assert RepositoryService.build_collection_name("https://github.com/ExampleOrg/MyRepo") == "exampleorg__myrepo"
