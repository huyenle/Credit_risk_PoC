"""Raw-source loading with a Git-LFS pointer guard.

The regulatory source files in ``data/regulations/`` are stored in Git LFS. A
clone made without ``git lfs pull`` leaves a small text *pointer* in the working
tree instead of the real bytes. Parsing that pointer would silently produce
garbage chunks, so every raw read goes through here and fails loudly with
instructions instead.
"""

from __future__ import annotations

from pathlib import Path

# A Git-LFS pointer file is a few lines of ASCII beginning with this line.
_LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"
# Real sources are far larger; pointers are well under this.
_MAX_POINTER_BYTES = 1024

REPO_ROOT = Path(__file__).resolve().parents[3]
REGULATIONS_DIR = REPO_ROOT / "data" / "regulations"


class LFSPointerError(RuntimeError):
    """Raised when a raw source file is an unresolved Git-LFS pointer."""


def _looks_like_pointer(head: bytes) -> bool:
    return head.lstrip()[: len(_LFS_POINTER_PREFIX)] == _LFS_POINTER_PREFIX


def check_resolved(path: Path | str) -> Path:
    """Return ``path`` if it exists and is real content, else raise.

    Raises ``FileNotFoundError`` if missing and :class:`LFSPointerError` if the
    file is still a Git-LFS pointer (clear instruction to run ``git lfs pull``).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"regulatory source not found: {p}")
    with open(p, "rb") as fh:
        head = fh.read(_MAX_POINTER_BYTES)
    if _looks_like_pointer(head):
        raise LFSPointerError(
            f"{p} is an unresolved Git-LFS pointer, not the real file. "
            f"Run `git lfs pull` (or `git lfs fetch --all && git lfs checkout`) "
            f"to download the content, then retry."
        )
    return p


def read_text(path: Path | str, encoding: str = "utf-8") -> str:
    """Read a raw source file's text after confirming it is not an LFS pointer."""
    p = check_resolved(path)
    return p.read_text(encoding=encoding)
