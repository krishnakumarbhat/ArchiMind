"""Central configuration for ArchiMind runtime, storage, and indexing."""

import os

from dotenv import load_dotenv


load_dotenv()


def _get_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default


def _get_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


_KNOWN_DB_SCHEMES = {"sqlite", "postgresql", "postgres", "mysql", "mssql", "oracle"}


def _normalize_database_url(raw_url: str) -> str:
    # Reject values that are clearly not database URLs (e.g. raw tokens).
    scheme_part = raw_url.split("://", 1)[0].split("+", 1)[0].lower() if "://" in raw_url else ""
    if not scheme_part or scheme_part not in _KNOWN_DB_SCHEMES:
        return ""

    if raw_url.startswith("postgres://"):
        return f"postgresql+psycopg://{raw_url[len('postgres://'):]}"

    if raw_url.startswith("postgresql://") and "+psycopg" not in raw_url:
        return f"postgresql+psycopg://{raw_url[len('postgresql://'):]}"

    if raw_url in {"sqlite:///:memory:", "sqlite+pysqlite:///:memory:"}:
        return raw_url

    if raw_url.startswith("sqlite:///") and not raw_url.startswith("sqlite:////"):
        relative_path = raw_url[len("sqlite:///"):]
        if not os.path.isabs(relative_path):
            return f"sqlite:///{os.path.abspath(relative_path)}"

    return raw_url


# --- File and Directory Settings ---
DATA_PATH = os.path.abspath("./data")
LOCAL_CLONE_PATH = os.path.join(DATA_PATH, "temp_repo")
VECTOR_STORE_PATH = os.path.join(DATA_PATH, "vector_store")
CHROMA_DB_PATH = VECTOR_STORE_PATH
SQLITE_DB_PATH = os.path.join(DATA_PATH, "archimind_dev.db")
SQLITE_URL = f"sqlite:///{SQLITE_DB_PATH}"
STATUS_FILE_PATH = os.path.join(DATA_PATH, "status.json")


def get_database_url() -> str:
    raw = os.getenv("DATABASE_URL", SQLITE_URL)
    normalized = _normalize_database_url(raw)
    if not normalized:
        import logging
        logging.getLogger(__name__).warning(
            "DATABASE_URL is not a recognized database URL; falling back to local SQLite."
        )
        return SQLITE_URL
    return normalized


def uses_sqlite(database_url: str | None = None) -> bool:
    return (database_url or get_database_url()).startswith("sqlite")


# --- Local model/indexing settings ---
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
VECTOR_BACKEND = os.getenv("VECTOR_BACKEND", "pinecone" if os.getenv("PINECONE_API_KEY") else "local")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "archimind")
PINECONE_HOST = os.getenv("PINECONE_HOST")
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "default")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")
PINECONE_DIMENSION = _get_int("PINECONE_DIMENSION", 768)
SMALL_SUMMARY_MODEL = os.getenv("SMALL_SUMMARY_MODEL", "heuristic")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
DOCUMENTATION_MODEL = os.getenv("DOCUMENTATION_MODEL", "gemini-3.1-flash-lite-preview")
CHAT_MODEL = os.getenv("CHAT_MODEL", DOCUMENTATION_MODEL)
GEMINI_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "high")
GEMINI_API_VERSION = os.getenv("GEMINI_API_VERSION", "v1alpha")
DOCUMENTATION_CONTEXT_CHAR_LIMIT = _get_int("DOCUMENTATION_CONTEXT_CHAR_LIMIT", 36000)
REMOTE_FETCH_MAX_FILES = _get_int("REMOTE_FETCH_MAX_FILES", 120)
REMOTE_FETCH_CONCURRENCY = _get_int("REMOTE_FETCH_CONCURRENCY", 8)
REMOTE_FILE_MAX_BYTES = _get_int("REMOTE_FILE_MAX_BYTES", 220000)
REQUEST_TIMEOUT_SECONDS = _get_int("REQUEST_TIMEOUT_SECONDS", 25)
ANONYMOUS_GENERATION_LIMIT = _get_int("ANONYMOUS_GENERATION_LIMIT", 5)
ENABLE_PERFORMANCE_HINTS = _get_bool("ENABLE_PERFORMANCE_HINTS", True)

# --- Repository scanning rules ---
ALLOWED_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".js",
    ".ts",
    ".html",
    ".css",
    ".json",
    ".yaml",
    ".yml",
    ".sh",
    "Dockerfile",
}
IGNORED_DIRECTORIES = {
    ".git",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".vscode",
    "venv",
    ".idea",
}