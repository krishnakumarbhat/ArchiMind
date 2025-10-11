"""Code Parser Agent for fetching repository structure using GitPython and GitHub API."""
from __future__ import annotations

import base64
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from config import MAX_CODE_FILES, MAX_FILE_SIZE, get_github_token
from repository_service import RepositoryService
from .base import AgentContext, BaseAgent

LOGGER = logging.getLogger(__name__)


def parse_github_url(url: str) -> Tuple[str, str]:
    pattern = r"github\.com[:/](?P<owner>[\w\-\.]+)/(?P<repo>[\w\-\.]+)"
    match = re.search(pattern, url)
    if not match:
        raise ValueError(f"Invalid GitHub repository URL: {url}")
    owner = match.group("owner")
    repo = match.group("repo")
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo


def get_repo_metadata(session: requests.Session, owner: str, repo: str) -> Dict[str, Any]:
    url = f"https://api.github.com/repos/{owner}/{repo}"
    response = session.get(url, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch repo metadata: {response.status_code} - {response.text}"
        )
    return response.json()


def get_repository_tree(session: requests.Session, owner: str, repo: str, branch: str) -> List[Dict[str, Any]]:
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    response = session.get(url, timeout=60)
    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch repository tree: {response.status_code} - {response.text}"
        )
    payload = response.json()
    return payload.get("tree", [])


def get_blob_content(session: requests.Session, owner: str, repo: str, sha: str) -> Optional[str]:
    url = f"https://api.github.com/repos/{owner}/{repo}/git/blobs/{sha}"
    response = session.get(url, timeout=30)
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


def fetch_files(
    session: requests.Session,
    owner: str,
    repo: str,
    tree: List[Dict[str, Any]],
    max_file_size: int,
    max_files: int,
) -> List[Dict[str, Any]]:
    files: List[Dict[str, Any]] = []
    for item in tree:
        if item.get("type") != "blob":
            continue
        size = item.get("size", 0)
        if size > max_file_size:
            LOGGER.debug("Skipping %s due to size %s", item.get("path"), size)
            continue
        if len(files) >= max_files:
            LOGGER.info(
                "Reached max file limit (%s). Skipping remaining files.", max_files
            )
            break
        content = get_blob_content(session, owner, repo, item.get("sha"))
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


class CodeParserAgent(BaseAgent):
    """Fetch repository metadata and file contents using GitPython with GitHub API fallback."""

    GITHUB_API_BASE = "https://api.github.com"

    def __init__(
        self,
        github_token: Optional[str] = None,
        max_files: int = MAX_CODE_FILES,
        max_file_size: int = MAX_FILE_SIZE,
    ) -> None:
        super().__init__(name="code_parser_agent")
        # GitHub token is commented out as requested - using GitPython cloning instead
        # self.github_token = github_token or get_github_token()
        self.max_files = max_files
        self.max_file_size = max_file_size
        self.repository_service = RepositoryService()
        
        # Keep GitHub API session for fallback/metadata only
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "User-Agent": "ArchiMind-Parser-Agent",
        })
        # if self.github_token:
        #     self.session.headers["Authorization"] = f"Bearer {self.github_token}"

    def run(self, context: AgentContext) -> AgentContext:
        repo_input = context.get("repo_url") or context.get("repo_input")
        if not repo_input:
            raise ValueError("CodeParserAgent requires 'repo_url' in context")

        LOGGER.info(f"Analyzing repository: {repo_input}")
        
        try:
            # Use GitPython-based repository service
            result = self.repository_service.analyze_repository(repo_input)
            
            context = self.update_context(
                context,
                repo_meta=result["repo_meta"],
                code_files=result["code_files"],
                repo_path=result["repo_path"]
            )
            return context
            
        except Exception as e:
            # Fallback to GitHub API for GitHub URLs if GitPython fails
            if "github.com" in repo_input:
                LOGGER.warning(f"GitPython failed, falling back to GitHub API: {str(e)}")
                return self._fallback_github_api(context, repo_input)
            else:
                raise e

    def _fallback_github_api(self, context: AgentContext, repo_url: str) -> AgentContext:
        """Fallback method using GitHub API when GitPython fails."""
        owner, repo = parse_github_url(repo_url)
        LOGGER.info("Using GitHub API fallback for %s/%s", owner, repo)
        
        repo_meta = get_repo_metadata(self.session, owner, repo)
        default_branch = repo_meta.get("default_branch", "main")

        tree = get_repository_tree(self.session, owner, repo, default_branch)
        files = fetch_files(
            self.session,
            owner,
            repo,
            tree,
            self.max_file_size,
            self.max_files,
        )

        context = self.update_context(
            context,
            repo_meta=repo_meta,
            file_tree=tree,
            code_files=files,
        )
        return context
    
    def cleanup(self):
        """Clean up any temporary resources."""
        if hasattr(self, 'repository_service'):
            self.repository_service.cleanup()
 
