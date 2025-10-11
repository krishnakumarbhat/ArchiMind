"""Repository service using GitPython for cloning and analyzing repositories."""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import git
from git import Repo

from config import MAX_CODE_FILES, MAX_FILE_SIZE

LOGGER = logging.getLogger(__name__)

# Supported code file extensions for analysis
CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.hpp', '.cs', '.go',
    '.rs', '.php', '.rb', '.scala', '.kt', '.swift', '.m', '.mm', '.dart',
    '.vue', '.jsx', '.tsx', '.html', '.css', '.scss', '.sass', '.less',
    '.yaml', '.yml', '.json', '.xml', '.toml', '.ini', '.cfg', '.config',
    '.sql', '.sh', '.bash', '.ps1', '.bat', '.dockerfile', '.md', '.rst',
    '.txt', '.gradle', '.sbt', '.pom', '.cmake', '.make', '.makefile'
}


class RepositoryService:
    """Handles repository cloning and file analysis using GitPython."""
    
    def __init__(self):
        # GitHub token is commented out as requested
        # self.github_token = get_github_token()
        self.temp_dirs: List[str] = []
    
    def analyze_repository(self, repo_input: str) -> Dict[str, object]:
        """
        Analyze a repository by URL or local path.
        
        Args:
            repo_input: Repository URL or local path
            
        Returns:
            Dictionary containing repo metadata and code files
        """
        if self._is_local_path(repo_input):
            return self._analyze_local_repository(repo_input)
        else:
            return self._analyze_remote_repository(repo_input)
    
    def _is_local_path(self, path: str) -> bool:
        """Check if input is a local file path."""
        return os.path.exists(path) or not path.startswith(('http://', 'https://'))
    
    def _analyze_local_repository(self, repo_path: str) -> Dict[str, object]:
        """Analyze a local repository."""
        try:
            repo = Repo(repo_path)
            repo_meta = self._extract_repo_metadata(repo, repo_path)
            code_files = self._extract_code_files(repo_path)
            
            return {
                "repo_meta": repo_meta,
                "code_files": code_files,
                "repo_url": repo_path,
                "repo_path": repo_path
            }
        except git.exc.InvalidGitRepositoryError:
            LOGGER.warning(f"Not a git repository: {repo_path}, analyzing as directory")
            return self._analyze_directory(repo_path)
    
    def _analyze_remote_repository(self, repo_url: str) -> Dict[str, object]:
        """Clone and analyze a remote repository."""
        temp_dir = tempfile.mkdtemp(prefix="archimind_repo_")
        self.temp_dirs.append(temp_dir)
        
        try:
            LOGGER.info(f"Cloning repository: {repo_url}")
            
            # Clone repository with GitPython
            # Note: GitHub token authentication is commented out
            clone_url = repo_url
            # if self.github_token and 'github.com' in repo_url:
            #     # Add token to URL for private repositories
            #     parsed = urlparse(repo_url)
            #     clone_url = f"https://{self.github_token}@{parsed.netloc}{parsed.path}"
            
            repo = Repo.clone_from(clone_url, temp_dir, depth=1)
            
            repo_meta = self._extract_repo_metadata(repo, repo_url)
            code_files = self._extract_code_files(temp_dir)
            
            return {
                "repo_meta": repo_meta,
                "code_files": code_files,
                "repo_url": repo_url,
                "repo_path": temp_dir
            }
            
        except Exception as e:
            LOGGER.error(f"Failed to clone repository {repo_url}: {str(e)}")
            raise
    
    def _analyze_directory(self, dir_path: str) -> Dict[str, object]:
        """Analyze a directory that's not a git repository."""
        repo_meta = {
            "name": os.path.basename(dir_path),
            "description": "Local directory (not a git repository)",
            "default_branch": "main",
            "language": "Unknown"
        }
        
        code_files = self._extract_code_files(dir_path)
        
        return {
            "repo_meta": repo_meta,
            "code_files": code_files,
            "repo_url": dir_path,
            "repo_path": dir_path
        }
    
    def _extract_repo_metadata(self, repo: Repo, repo_identifier: str) -> Dict[str, str]:
        """Extract metadata from a git repository."""
        try:
            # Get repository name
            if hasattr(repo.remotes, 'origin') and repo.remotes.origin.exists():
                origin_url = repo.remotes.origin.url
                repo_name = os.path.basename(origin_url.rstrip('.git'))
            else:
                repo_name = os.path.basename(repo.working_dir)
            
            # Get default branch
            try:
                default_branch = repo.active_branch.name
            except:
                default_branch = "main"
            
            return {
                "name": repo_name,
                "description": f"Repository: {repo_identifier}",
                "default_branch": default_branch,
                "language": self._detect_primary_language(repo.working_dir)
            }
        except Exception as e:
            LOGGER.warning(f"Error extracting repo metadata: {str(e)}")
            return {
                "name": "Unknown",
                "description": f"Repository: {repo_identifier}",
                "default_branch": "main",
                "language": "Unknown"
            }
    
    def _extract_code_files(self, repo_path: str) -> List[Dict[str, object]]:
        """Extract code files from repository."""
        code_files = []
        repo_path_obj = Path(repo_path)
        
        # Walk through all files in the repository
        for file_path in repo_path_obj.rglob('*'):
            if self._should_include_file(file_path):
                try:
                    relative_path = file_path.relative_to(repo_path_obj)
                    file_size = file_path.stat().st_size
                    
                    if file_size > MAX_FILE_SIZE:
                        LOGGER.debug(f"Skipping large file: {relative_path} ({file_size} bytes)")
                        continue
                    
                    # Read file content
                    try:
                        content = file_path.read_text(encoding='utf-8', errors='ignore')
                    except Exception as e:
                        LOGGER.warning(f"Could not read file {relative_path}: {str(e)}")
                        continue
                    
                    code_files.append({
                        "path": str(relative_path),
                        "content": content,
                        "size": file_size,
                        "extension": file_path.suffix
                    })
                    
                    if len(code_files) >= MAX_CODE_FILES:
                        LOGGER.info(f"Reached maximum file limit ({MAX_CODE_FILES}), stopping")
                        break
                        
                except Exception as e:
                    LOGGER.warning(f"Error processing file {file_path}: {str(e)}")
                    continue
        
        LOGGER.info(f"Extracted {len(code_files)} code files")
        return code_files
    
    def _should_include_file(self, file_path: Path) -> bool:
        """Determine if a file should be included in analysis."""
        if not file_path.is_file():
            return False
        
        # Skip hidden files and directories
        if any(part.startswith('.') for part in file_path.parts):
            return False
        
        # Skip common build/dependency directories
        skip_dirs = {
            'node_modules', '__pycache__', '.git', 'venv', 'env', 'build', 
            'dist', 'target', 'bin', 'obj', '.vscode', '.idea', 'vendor'
        }
        if any(part in skip_dirs for part in file_path.parts):
            return False
        
        # Include files with supported extensions
        return file_path.suffix.lower() in CODE_EXTENSIONS
    
    def _detect_primary_language(self, repo_path: str) -> str:
        """Detect the primary programming language in the repository."""
        language_counts = {}
        repo_path_obj = Path(repo_path)
        
        for file_path in repo_path_obj.rglob('*'):
            if file_path.is_file() and file_path.suffix:
                ext = file_path.suffix.lower()
                language_counts[ext] = language_counts.get(ext, 0) + 1
        
        if not language_counts:
            return "Unknown"
        
        # Map extensions to languages
        ext_to_language = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.cs': 'C#',
            '.go': 'Go',
            '.rs': 'Rust',
            '.php': 'PHP',
            '.rb': 'Ruby',
            '.scala': 'Scala',
            '.kt': 'Kotlin',
            '.swift': 'Swift'
        }
        
        most_common_ext = max(language_counts, key=language_counts.get)
        return ext_to_language.get(most_common_ext, most_common_ext.upper())
    
    def cleanup(self) -> None:
        """Clean up temporary directories."""
        for temp_dir in self.temp_dirs:
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    LOGGER.info(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                LOGGER.warning(f"Failed to clean up {temp_dir}: {str(e)}")
        self.temp_dirs.clear()
    
    def __del__(self):
        """Ensure cleanup on object destruction."""
        self.cleanup()
