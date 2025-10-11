"""Code Parser Agent for fetching repository structure via GitHub API."""
from __future__ import annotations

import base64
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from config import MAX_CODE_FILES, MAX_FILE_SIZE
from .base import AgentContext, BaseAgent

LOGGER = logging.getLogger(__name__)


class CodeParserAgent(BaseAgent):
    """Fetch repository metadata and file contents using the GitHub API."""

    GITHUB_API_BASE = "https://api.github.com"

    def __init__(
        self,
        github_token: Optional[str] = None,
        max_files: int = MAX_CODE_FILES,
        max_file_size: int = MAX_FILE_SIZE,
    ) -> None:
        super().__init__(name="code_parser_agent")
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        self.max_files = max_files
        self.max_file_size = max_file_size
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "User-Agent": "ArchiMind-Parser-Agent",
        })
        if self.github_token:
            self.session.headers["Authorization"] = f"Bearer {self.github_token}"

    def run(self, context: AgentContext) -> AgentContext:
        repo_url = context.get("repo_url") or context.get("repo_input")
        if not repo_url:
            raise ValueError("CodeParserAgent requires 'repo_url' in context")

        owner, repo = self._parse_github_url(repo_url)
        LOGGER.info("Fetching metadata for %s/%s", owner, repo)
        repo_meta = self._get_repo_metadata(owner, repo)
        default_branch = repo_meta.get("default_branch", "main")

        tree = self._get_repository_tree(owner, repo, default_branch)
        files = self._fetch_files(owner, repo, tree)

        context = self.update_context(
            context,
            repo_meta=repo_meta,
            file_tree=tree,
            code_files=files,
        )
        return context

    def _parse_github_url(self, url: str) -> Tuple[str, str]:
        pattern = r"github\.com[:/](?P<owner>[\w\-\.]+)/(?P<repo>[\w\-\.]+)"
        match = re.search(pattern, url)
        if not match:
            raise ValueError(f"Invalid GitHub repository URL: {url}")
        owner = match.group("owner")
        repo = match.group("repo")
        if repo.endswith(".git"):
            repo = repo[:-4]
        return owner, repo

    def _get_repo_metadata(self, owner: str, repo: str) -> Dict[str, Any]:
        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}"
        response = self.session.get(url, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch repo metadata: {response.status_code} - {response.text}"
            )
        return response.json()

    def _get_repository_tree(self, owner: str, repo: str, branch: str) -> List[Dict[str, Any]]:
        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        response = self.session.get(url, timeout=60)
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch repository tree: {response.status_code} - {response.text}"
            )
        payload = response.json()
        return payload.get("tree", [])

    def _fetch_files(
        self,
        owner: str,
        repo: str,
        tree: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        files: List[Dict[str, Any]] = []
        for item in tree:
            if item.get("type") != "blob":
                continue
            size = item.get("size", 0)
            if size > self.max_file_size:
                LOGGER.debug("Skipping %s due to size %s", item.get("path"), size)
                continue
            if len(files) >= self.max_files:
                LOGGER.info(
                    "Reached max file limit (%s). Skipping remaining files.", self.max_files
                )
                break
            content = self._get_blob_content(owner, repo, item.get("sha"))
            if content is None:
                continue
            files.append(
                {
                    "path": item.get("path"),
                    "size": size,
                    "content": content,
                }
            )
        return files

    def _get_blob_content(self, owner: str, repo: str, sha: str) -> Optional[str]:
        url = f"{self.GITHUB_API_BASE}/repos/{owner}/{repo}/git/blobs/{sha}"
        response = self.session.get(url, timeout=30)
        if response.status_code != 200:
            LOGGER.warning(
                "Failed to fetch blob %s: %s - %s", sha, response.status_code, response.text
            )
            return None
        payload = response.json()
        encoding = payload.get("encoding")
        if encoding != "base64":
            LOGGER.warning("Unexpected blob encoding %s for %s", encoding, sha)
            return None
        try:
            content_bytes = base64.b64decode(payload.get("content", ""), validate=True)
            return content_bytes.decode("utf-8", errors="ignore")
        except Exception as exc:
            LOGGER.warning("Error decoding blob %s: %s", sha, exc)
            return None


def build_code_parser_agent(context: Optional[Dict[str, Any]] = None) -> CodeParserAgent:
    """Factory function for dependency injection / testing."""
    _ = context  # placeholder for future dependency injection
    return CodeParserAgent()
