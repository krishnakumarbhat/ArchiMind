"""Build the golden-repo precache: tarball -> CPG -> deterministic diagrams -> SQLite."""
import logging
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config._00_settings import SETTINGS  # noqa: E402
from src.config._01_constants import GOLDEN_REPOS  # noqa: E402
from src.cpg._01_cpg_builder import NODE_CLASS, NODE_FILE, NODE_FUNC, build_graph, to_compact  # noqa: E402
from src.governance._01_invariants import check_invariants  # noqa: E402
from src.ingestion._00_tarball_client import stream_files  # noqa: E402
from src.ingestion._01_file_filter import decode_sources  # noqa: E402
from src.storage._00_sqlite_cache import CacheStore  # noqa: E402
from src.storage._01_golden_repos import golden_key  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("golden")


def _node_id(raw: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9]", "", raw)
    return (clean[:24] or "n") if clean[:1].isalpha() else f"n{clean[:24]}"


def deterministic_hld(g, limit: int = 14) -> str:
    """Valid-by-construction HLD: top files by out-degree -> their classes."""
    outdeg = sorted(g.out_degree, key=lambda t: t[1], reverse=True)
    files = [n for n, _ in outdeg if g.nodes[n].get("kind") == NODE_FILE][:limit]
    lines = ["graph TD"]
    for f in files:
        fid = _node_id(f)
        label = (g.nodes[f].get("path") or f).split("/")[-1][:28]
        lines.append(f"    {fid}[{label}]")
        classes = [n for n in g.successors(f) if g.nodes[n].get("kind") == NODE_CLASS][:6]
        for c in classes:
            cid = _node_id(c)
            lines.append(f"    {cid}[{g.nodes[c].get('name', c)[:24]}]")
            lines.append(f"    {fid} --> {cid}")
    return "\n".join(lines)


def build_one(repo_id: str, repo_url: str, description: str) -> dict:
    """Ingest one repo and return its golden artifact document."""
    raw, meta = stream_files(repo_url)
    rel = {name.split("/", 1)[1] if "/" in name else name: blob for name, blob in raw.items()}
    sources = decode_sources({k: v for k, v in rel.items()})
    py_files = {k: v for k, v in sources.items() if k.endswith(".py")}
    g = build_graph(dict(list(py_files.items())[:250]))
    stats = {
        "files": len(sources),
        "py_files": len(py_files),
        "classes": sum(1 for _, d in g.nodes(data=True) if d.get("kind") == NODE_CLASS),
        "functions": sum(1 for _, d in g.nodes(data=True) if d.get("kind") == NODE_FUNC),
        "edges": g.number_of_edges(),
    }
    short = repo_url.rstrip("/").split("/")[-2:]
    name = "/".join(short)
    return {
        "id": repo_id,
        "name": name,
        "repo_url": repo_url,
        "description": description,
        "stats": stats,
        "chat_summary": (
            f"{name}: {stats['py_files']} Python files, {stats['classes']} classes, "
            f"{stats['functions']} functions, {stats['edges']} structural edges."
        ),
        "hld_mermaid": deterministic_hld(g),
        "invariants": check_invariants(g),
        "cpg_artifact": to_compact(g),
    }


def main() -> None:
    """Build all golden artifacts into the SQLite cache."""
    store = CacheStore(os.path.join(SETTINGS.data_path, "golden.db"))
    for repo_id, url, desc in GOLDEN_REPOS:
        try:
            doc = build_one(repo_id, url, desc)
        except Exception as exc:
            logger.error("Golden build failed for %s: %s", repo_id, exc)
            continue
        store.put(golden_key(repo_id), doc)
        logger.info("Golden cached: %s (%s)", repo_id, doc["stats"])


if __name__ == "__main__":
    main()
