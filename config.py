# config.py
"""
Central configuration file for the RAG Documentation Generator.
Loads sensitive data from environment variables.
"""
import os
from dotenv import load_dotenv

# Load environment variables from a .env file (optional)
load_dotenv()

# --- API Keys ---
# It is highly recommended to use environment variables for API keys.
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")

# --- Models ---
EMBEDDING_MODEL = 'nomic-embed-text'
GENERATION_MODEL = 'gemini-2.5-pro' # Using a more recent model
CHAT_MODEL = 'gemini-2.5-flash'

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
STATUS_FILE_PATH = os.path.join(DATA_PATH, 'status.json')