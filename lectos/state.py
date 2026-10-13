"""Lecture recovery state: one small JSON file per PDF under the XDG state directory."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

MAX_STATE_BYTES = 16 * 1024
MAX_INK_BYTES = 8 * 1024 * 1024


def state_path(pdf: Path, kind: str = "") -> Path:
    """Return the state file for the PDF (``kind`` selects e.g. the ink file), creating no files."""
    root = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "lectos"
    digest = hashlib.sha256(str(pdf.resolve()).encode()).hexdigest()[:16]
    return root / (f"{digest}.{kind}.json" if kind else f"{digest}.json")


def load(pdf: Path, kind: str = "") -> dict[str, object]:
    """Return saved state, or an empty dict if absent or unreadable."""
    try:
        data = json.loads(state_path(pdf, kind).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(pdf: Path, data: dict[str, object], kind: str = "") -> None:
    """Atomically replace the state file."""
    text = json.dumps(data)
    if len(text) > (MAX_INK_BYTES if kind == "ink" else MAX_STATE_BYTES):
        raise ValueError(f"{kind or 'state'} too large")
    path = state_path(pdf, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".state-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
