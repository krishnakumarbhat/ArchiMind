"""Stream shallow GitHub tarballs into memory (no git clone)."""
import io
import logging
import tarfile
import urllib.request
from typing import Dict, Tuple

from src.config._00_settings import SETTINGS

logger = logging.getLogger(__name__)


def repo_tarball_url(repo_url: str, ref: str = "HEAD") -> str:
    """Convert a github.com/owner/repo URL into a codeload tarball URL."""
    parts = repo_url.rstrip("/").split("/")
    if len(parts) < 5 or "github.com" not in parts[2]:
        raise ValueError(f"Not a GitHub repository URL: {repo_url}")
    return f"https://codeload.github.com/{parts[3]}/{parts[4]}/tar.gz/{ref}"


def stream_files(
    repo_url: str,
    max_mb: int = SETTINGS.tarball_max_mb,
    timeout_s: int = SETTINGS.tarball_timeout_s,
) -> Tuple[Dict[str, bytes], Dict[str, object]]:
    """Download tarball in 64KB chunks; return {arcname: raw bytes} + meta."""
    from src.ingestion._01_file_filter import keep_member  # deferred: same package

    url = repo_tarball_url(repo_url)
    buf = io.BytesIO()
    req = urllib.request.Request(url, headers={"User-Agent": "archimind-engine"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            buf.write(chunk)
            if buf.tell() > max_mb * 1_000_000:
                raise RuntimeError(f"Tarball exceeds {max_mb}MB cap")
    buf.seek(0)
    out: Dict[str, bytes] = {}
    skipped = 0
    with tarfile.open(fileobj=buf, mode="r|gz") as tar:
        for member in tar:
            if not member.isfile():
                continue
            if not keep_member(member.name, member.size):
                skipped += 1
                continue
            fh = tar.extractfile(member)
            if fh is None:
                skipped += 1
                continue
            try:
                out[member.name] = fh.read()
            except Exception as exc:
                logger.warning("Unreadable member %s: %s", member.name, exc)
                skipped += 1
    meta = {"url": url, "files": len(out), "skipped": skipped, "bytes": buf.tell()}
    logger.info("Tarball %s: %d files, %d skipped", repo_url, len(out), skipped)
    return out, meta
