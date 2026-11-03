"""Lecture recovery state: one small JSON file per PDF under the XDG state directory."""

from __future__ import annotations

import faulthandler
import hashlib
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from lectos.paths import write_atomic

MAX_STATE_BYTES = 16 * 1024
MAX_INK_BYTES = 8 * 1024 * 1024
LAST_FOLDER_FILE = "last-folder.txt"
CRASH_LOG_FILE = "crash.log"


def _root() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "lectos"


def state_path(pdf: Path, kind: str = "") -> Path:
    """Return the state file for the PDF (``kind`` selects e.g. the ink file), creating no files."""
    root = _root()
    digest = hashlib.sha256(str(pdf.resolve()).encode()).hexdigest()[:16]
    return root / (f"{digest}.{kind}.json" if kind else f"{digest}.json")


@contextmanager
def crash_log() -> Iterator[None]:
    """While active, a fatal signal (segmentation fault, abort) writes the Python traceback to ``crash.log``."""
    try:
        path = _root() / CRASH_LOG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a", encoding="utf-8")
    except OSError:
        yield  # a diagnostic only: never block starting
        return
    with handle:
        faulthandler.enable(handle)
        try:
            yield
        finally:
            faulthandler.disable()


def last_folder() -> Path | None:
    """The folder the file chooser last picked from, if it still exists."""
    try:
        folder = Path((_root() / LAST_FOLDER_FILE).read_text(encoding="utf-8").strip())
    except OSError:
        return None
    return folder if folder.is_dir() else None


def remember_folder(folder: Path) -> None:
    """Keep ``folder`` as the place the file chooser opens in next time."""
    try:
        write_atomic(_root() / LAST_FOLDER_FILE, str(folder))
    except OSError:
        return  # a convenience only: never block opening files


def edits_path(pdf: Path) -> Path:
    """Where edited notes for a Beamer deck are kept (a Markdown file; the .tex is never touched)."""
    return state_path(pdf, "notes").with_suffix(".md")


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
