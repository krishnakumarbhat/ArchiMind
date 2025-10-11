# repo_manager.py
"""
Manages cloning of a Git repository and reading its files.
"""
import os
import git
import logging
from typing import Dict, Set

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def clone_repo(repo_url: str, local_path: str) -> bool:
    """Clones a GitHub repository if the local path doesn't exist."""
    if os.path.exists(local_path):
        logging.info(f"Repository already exists at: {local_path}. Skipping clone.")
        return True

    logging.info(f"Cloning repository from {repo_url} to {local_path}...")
    try:
        git.Repo.clone_from(repo_url, local_path)
        logging.info("Repository cloned successfully.")
        return True
    except git.exc.GitCommandError as e:
        logging.error(f"Error cloning repository: {e}")
        return False

def read_repo_files(
    repo_path: str,
    allowed_extensions: Set[str],
    ignored_dirs: Set[str]
) -> Dict[str, str]:
    """Reads all allowed text files from the repository."""
    file_contents = {}
    logging.info("Reading files from the repository...")

    for root, dirs, files in os.walk(repo_path):
        # Filter out ignored directories
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for file in files:
            if any(file.endswith(ext) for ext in allowed_extensions):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        relative_path = os.path.relpath(file_path, repo_path)
                        file_contents[relative_path] = f.read()
                except Exception as e:
                    logging.warning(f"Could not read file {file_path}: {e}")

    logging.info(f"Found and read {len(file_contents)} files.")
    return file_contents