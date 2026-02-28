# config.py
"""Central configuration for ArchiMind runtime and indexing."""
import os
from dotenv import load_dotenv

# Load environment variables from a .env file (optional)
load_dotenv()

# --- Local model/indexing settings ---
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'chroma-default')
SMALL_SUMMARY_MODEL = os.getenv('SMALL_SUMMARY_MODEL', 'heuristic')

# --- File and Directory Settings ---
ALLOWED_EXTENSIONS = {
    '.py', '.md', '.txt', '.js', '.ts', '.html', '.css',
    '.json', '.yaml', '.yml', '.sh', 'Dockerfile'
}
IGNORED_DIRECTORIES = {
    '.git', '__pycache__', 'node_modules', 'dist',
    'build', '.vscode', 'venv', '.idea'
}

# --- Database and Local Paths ---
DATA_PATH = os.path.abspath('./data')
LOCAL_CLONE_PATH = os.path.join(DATA_PATH, 'temp_repo')
CHROMA_DB_PATH = os.path.join(DATA_PATH, 'chroma_db')
SQLITE_DB_PATH = os.path.join(DATA_PATH, 'archimind_dev.db')
SQLITE_URL = f"sqlite:///{SQLITE_DB_PATH}"
STATUS_FILE_PATH = os.path.join(DATA_PATH, 'status.json')