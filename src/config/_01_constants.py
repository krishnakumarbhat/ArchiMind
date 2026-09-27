"""Shared resource bounds, file filters, and invariant thresholds."""

ALLOWED_EXTENSIONS = frozenset({".py", ".js", ".ts", ".tsx", ".jsx", ".mjs"})
CPG_EXTENSIONS = (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs")

IGNORED_DIRECTORIES = frozenset(
    {"tests", "test", "docs", "examples", "vendor", "node_modules", ".git", "__pycache__", "dist", "build"}
)

SKIP_SUFFIXES = frozenset({".png", ".jpg", ".mp4", ".gif", ".ico", ".woff", ".ttf", ".bin", ".so", ".min.js"})

MAX_FILE_BYTES = 200_000
DUNDER_EXEMPT_BASE = "object"

INVARIANT_PRESENTATION_ISOLATION = "presentation-isolation"
INVARIANT_ACYCLIC = "acyclic-dependencies"
INVARIANT_DOMAIN_PURITY = "domain-purity"

# (id, title, subtitle, repo, subtree dirs) — bundled as src/storage/golden_fixtures/<id>.json
GOLDEN_REPOS = (
    ("pytorch", "PyTorch Core", "Tensor & nn module subsystem", "pytorch/pytorch", ("torch/nn/modules", "torch/optim")),
    ("openclaw", "OpenClaw", "Agentic runtime subsystem", "openclaw/openclaw", ("src/agents/harness", "src/agents")),
    ("requests", "Requests HTTP", "Distributed client architecture", "psf/requests", ("src/requests",)),
)
