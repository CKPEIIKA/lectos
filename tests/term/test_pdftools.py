import shutil
import subprocess
from pathlib import Path

import pytest

from lectos.term import pdftools
from lectos.term.pdftools import PdfToolError

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "slides.pdf"
needs_text_tools = pytest.mark.skipif(
    not (shutil.which("pdfinfo") and shutil.which("pdftotext")), reason="needs poppler-utils"
)
needs_previews = pytest.mark.skipif(not pdftools.previews_available(), reason="needs pdftoppm and chafa")


@needs_text_tools
@pytest.mark.integration
def test_page_count_and_texts_come_from_poppler() -> None:
    assert pdftools.page_count(EXAMPLE) == 8
    texts = pdftools.page_texts(EXAMPLE)
    assert len(texts) == 8
    assert "lectos" in texts[0]
    assert pdftools.page_texts(EXAMPLE) is texts  # cached per file version


@needs_previews
@pytest.mark.integration
def test_preview_is_ansi_text_without_cursor_control_and_is_cached() -> None:
    lines = pdftools.preview(EXAMPLE, 1, 40, 10)
    assert lines
    assert all("\x1b[?25" not in line for line in lines)  # chafa must not touch the cursor
    assert pdftools.preview(EXAMPLE, 1, 40, 10) == lines


def test_previews_need_both_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdftools.shutil, "which", lambda name: "/usr/bin/x" if name == "chafa" else None)
    assert pdftools.previews_available() is False
    monkeypatch.setattr(pdftools.shutil, "which", lambda name: "/usr/bin/x")
    assert pdftools.previews_available() is True


def test_run_reports_missing_failing_and_hanging_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(PdfToolError, match="failed"):
        pdftools._run(["definitely-not-a-real-tool"])
    with pytest.raises(PdfToolError, match="boom"):
        pdftools._run(["sh", "-c", "echo boom >&2; exit 3"])
    monkeypatch.setattr(pdftools, "TOOL_TIMEOUT_S", 0.2)
    with pytest.raises(PdfToolError, match="timed out"):
        pdftools._run(["sleep", "5"])
    assert pdftools._run(["printf", "ok"]) == b"ok"


def test_page_count_without_a_pages_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdftools, "_run", lambda _args: b"Title: nothing useful\n")
    with pytest.raises(PdfToolError, match="cannot determine page count"):
        pdftools.page_count(EXAMPLE)


def test_run_failure_wraps_subprocess_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise subprocess.TimeoutExpired("x", 1)

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(PdfToolError):
        pdftools._run(["anything"])
