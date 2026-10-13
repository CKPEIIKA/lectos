"""File name and file helpers. No GUI code."""

from __future__ import annotations

import os
import tempfile
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


NOTES_SUFFIXES = (".tex", ".md")
GENERIC_NOTES = ("notes.tex", "notes.md")


def notes_for(pdf: Path) -> Path | None:
    """Notes next to the slides: ``slides.tex`` or ``slides.md``, else ``notes.tex`` or ``notes.md`` in the folder."""
    names = [pdf.with_suffix(suffix).name for suffix in NOTES_SUFFIXES] + list(GENERIC_NOTES)
    return next((found for name in names if (found := pdf.with_name(name)).is_file()), None)


def discover(folder: Path) -> tuple[Path, Path | None] | None:
    """The slides in a folder and their notes: the first PDF that has notes, else the first PDF by name."""
    pdfs = sorted(p for p in folder.glob("*.pdf") if p.is_file())
    for pdf in pdfs:
        notes = notes_for(pdf)
        if notes is not None:
            return pdf, notes
    return (pdfs[0], None) if pdfs else None


def write_atomic(path: Path, text: str) -> None:
    """Replace ``path`` with ``text`` so a reader never sees a half-written file (creates the folder)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".lectos-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
