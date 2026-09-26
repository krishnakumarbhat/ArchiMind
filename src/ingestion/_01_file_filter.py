"""Path sanitizer and language extension matcher."""
import os
from typing import Dict

from src.config._00_settings import SETTINGS
from src.config._01_constants import ALLOWED_EXTENSIONS, IGNORED_DIRECTORIES, MAX_FILE_BYTES, SKIP_SUFFIXES


def keep_member(arcname: str, size: int) -> bool:
    """Decide whether a tarball member is analyzable source (bounded)."""
    if size > MAX_FILE_BYTES:
        return False
    parts = arcname.split("/")
    if any(p in IGNORED_DIRECTORIES for p in parts):
        return False
    leaf = parts[-1]
    if any(leaf.endswith(s) for s in SKIP_SUFFIXES):
        return False
    return os.path.splitext(leaf)[1].lower() in ALLOWED_EXTENSIONS


def decode_sources(raw: Dict[str, bytes], max_files: int = SETTINGS.tarball_max_files) -> Dict[str, str]:
    """Decode raw members to text keyed by basename; cap file count."""
    out: Dict[str, str] = {}
    for arcname in sorted(raw):
        if len(out) >= max_files:
            break
        leaf = arcname.split("/")[-1]
        if leaf in out:
            continue
        try:
            out[leaf] = raw[arcname].decode("utf-8", "replace")
        except Exception:
            continue
    return out
