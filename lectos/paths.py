"""File name helpers. No GUI code."""

from __future__ import annotations

from pathlib import Path

MAX_TRIES = 1000


def unique(path: Path) -> Path:
    """``path`` itself if free, else ``name-2.ext``, ``name-3.ext``, ...: never an existing file."""
    if not path.exists():
        return path
    for n in range(2, MAX_TRIES):
        candidate = path.with_name(f"{path.stem}-{n}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise OSError(f"no free name next to {path}")
