"""Shared resource bounds, file filters, and invariant thresholds."""

ALLOWED_EXTENSIONS = frozenset({".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java"})

IGNORED_DIRECTORIES = frozenset(
    {"tests", "test", "docs", "examples", "vendor", "node_modules", ".git", "__pycache__", "dist", "build"}
)

SKIP_SUFFIXES = frozenset({".png", ".jpg", ".mp4", ".gif", ".ico", ".woff", ".ttf", ".bin", ".so", ".min.js"})

MAX_FILE_BYTES = 200_000
DUNDER_EXEMPT_BASE = "object"

INVARIANT_PRESENTATION_ISOLATION = "presentation-isolation"
INVARIANT_ACYCLIC = "acyclic-dependencies"
INVARIANT_DOMAIN_PURITY = "domain-purity"

GOLDEN_REPOS = (
    ("flask", "https://github.com/pallets/flask", "Classic WSGI web framework"),
    ("requests", "https://github.com/psf/requests", "HTTP client with session adapters"),
    ("sqlmodel", "https://github.com/tiangolo/sqlmodel", "Pydantic + SQLAlchemy models"),
)
