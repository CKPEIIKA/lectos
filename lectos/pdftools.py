"""Poppler command-line tools and chafa for the terminal console: page count, text, previews."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

TOOL_TIMEOUT_S = 60.0
PREVIEW_DPI = 80
PREVIEW_CACHE = 64
# Never let chafa query or write to the terminal we are drawing on: probe replies would arrive as keystrokes.
CHAFA_ARGS = ("chafa", "--probe", "off", "--polite", "on", "-f", "symbols", "--colors", "full", "--animate", "off")
TEXT_CACHE = 2
FORM_FEED = "\f"
_CURSOR_RE = re.compile(r"\x1b\[\?25[lh]")


class PdfToolError(RuntimeError):
    """Raised when a poppler tool or chafa fails."""


def _run(args: list[str]) -> bytes:
    try:
        result = subprocess.run(
            args, capture_output=True, stdin=subprocess.DEVNULL, timeout=TOOL_TIMEOUT_S, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PdfToolError(f"{args[0]} failed: {exc}") from exc
    if result.returncode != 0:
        raise PdfToolError(f"{args[0]} failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def page_count(pdf: Path) -> int:
    """Number of pages, from ``pdfinfo``."""
    for line in _run(["pdfinfo", "--", str(pdf)]).decode(errors="replace").splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1])
    raise PdfToolError(f"cannot determine page count of {pdf}")


@lru_cache(maxsize=TEXT_CACHE)
def _texts(pdf: Path, mtime_ns: int) -> tuple[str, ...]:
    pages = _run(["pdftotext", "-layout", str(pdf), "-"]).decode(errors="replace").split(FORM_FEED)
    return tuple(pages[:-1] if pages and not pages[-1].strip() else pages)


def page_texts(pdf: Path) -> tuple[str, ...]:
    """Text of every page, extracted once per file version."""
    return _texts(pdf, pdf.stat().st_mtime_ns)


def previews_available() -> bool:
    """True when both ``pdftoppm`` and ``chafa`` are installed."""
    return shutil.which("pdftoppm") is not None and shutil.which("chafa") is not None


@lru_cache(maxsize=PREVIEW_CACHE)
def _preview(pdf: Path, mtime_ns: int, page: int, cols: int, rows: int) -> tuple[str, ...]:
    with tempfile.TemporaryDirectory(prefix="lectos-") as tmp:
        root = Path(tmp) / "p"
        number = str(page + 1)
        _run(
            ["pdftoppm", "-png", "-r", str(PREVIEW_DPI), "-f", number, "-l", number, "-singlefile", str(pdf), str(root)]
        )
        out = _run([*CHAFA_ARGS, "-s", f"{cols}x{rows}", str(root.with_suffix(".png"))])
    return tuple(_CURSOR_RE.sub("", out.decode(errors="replace")).splitlines())


def preview(pdf: Path, page: int, cols: int, rows: int) -> list[str]:
    """ANSI text lines showing the page, at most ``cols`` x ``rows`` cells."""
    return list(_preview(pdf, pdf.stat().st_mtime_ns, page, cols, rows))
