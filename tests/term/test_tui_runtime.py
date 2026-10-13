import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from lectos import state
from lectos.config import Options
from lectos.projectors.projection import NullProjector
from lectos.term import pdftools
from lectos.term import tui as tui_module
from lectos.term.tui import PdfInfo, Runner, Tui, make_tui, pdf_info, run_select
from lectos.term.tuiterm import Terminal

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
needs_poppler = pytest.mark.skipif(
    not (shutil.which("pdfinfo") and shutil.which("pdftotext")), reason="needs poppler-utils"
)


class FakeTerminal:
    """A scripted terminal: hands out batches of keys, then behaves like Ctrl-C."""

    def __init__(self, batches: list[list[str]] | None = None) -> None:
        self.batches = list(batches or [])
        self.drawn: list[list[str]] = []
        self.exited = False

    def __enter__(self) -> "FakeTerminal":
        return self

    def __exit__(self, *_args: object) -> None:
        self.exited = True

    @staticmethod
    def size() -> tuple[int, int]:
        return 100, 24

    def read_keys(self, _timeout: float) -> list[str]:
        if not self.batches:
            raise KeyboardInterrupt
        return self.batches.pop(0)

    def draw(self, lines: list[str]) -> None:
        self.drawn.append(lines)


@pytest.fixture
def deck_pdf(tmp_path: Path) -> Path:
    pdf = tmp_path / "slides.pdf"
    shutil.copy(EXAMPLES / "slides.pdf", pdf)
    return pdf


def make_runner(pdf: Path, terminal: FakeTerminal, extra_save: Callable[[], None] | None = None) -> tuple[Runner, Tui]:
    info = PdfInfo(8, lambda: ("a",) * 8)
    tui = Tui(None, Options(), NullProjector(), info, lambda: 1000.0)
    return Runner(tui, cast(Terminal, terminal), pdf, extra_save), tui


def test_a_step_handles_keys_and_draws_only_when_the_frame_changed(deck_pdf: Path) -> None:
    terminal = FakeTerminal()
    runner, tui = make_runner(deck_pdf, terminal)
    runner.step(["l"])
    assert tui.deck.view == 1
    assert len(terminal.drawn) == 1
    runner.step([])
    assert len(terminal.drawn) == 1  # nothing changed: no redraw
    runner.step(["l"])
    assert len(terminal.drawn) == 2


def test_autosave_writes_state_and_calls_the_extra_saver(deck_pdf: Path) -> None:
    saved: list[int] = []
    runner, tui = make_runner(deck_pdf, FakeTerminal(), lambda: saved.append(1))
    runner.step(["l", "l"])
    assert state.load(deck_pdf) == {}  # not yet: the first save is a couple of seconds away
    runner._next_save = 0.0
    runner.step([])
    assert state.load(deck_pdf)["page"] == 2
    assert saved == [1]
    assert tui.dirty is False


def test_a_state_file_that_cannot_be_written_is_reported_not_fatal(
    deck_pdf: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(*_a: object) -> None:
        raise OSError("read-only file system")

    monkeypatch.setattr(state, "save", boom)
    runner, _tui = make_runner(deck_pdf, FakeTerminal())
    runner.save()
    assert "cannot save state: read-only file system" in capsys.readouterr().err


@needs_poppler
def test_a_recompiled_pdf_is_picked_up_while_running(deck_pdf: Path) -> None:
    runner, tui = make_runner(deck_pdf, FakeTerminal())
    assert tui.deck.pages == 8
    stat = deck_pdf.stat()
    os.utime(deck_pdf, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))
    runner.step([])
    assert tui.deck.pages == 8  # the same document, re-read through poppler
    assert tui.pdf.preview is None or callable(tui.pdf.preview)


def test_run_select_loops_until_quit_and_saves(deck_pdf: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    terminal = FakeTerminal([["l"], [":", "q", "Enter"]])
    monkeypatch.setattr(tui_module, "Terminal", lambda: terminal)
    tui = Tui(None, Options(), NullProjector(), PdfInfo(8, lambda: ("a",) * 8), lambda: 1000.0)
    run_select(tui, deck_pdf)
    assert tui.running is False
    assert terminal.exited is True
    assert state.load(deck_pdf)["view"] == 1


def test_ctrl_c_in_the_select_loop_ends_quietly_but_still_saves(
    deck_pdf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    terminal = FakeTerminal([["l", "l"]])  # then the fake raises KeyboardInterrupt
    monkeypatch.setattr(tui_module, "Terminal", lambda: terminal)
    tui = Tui(None, Options(), NullProjector(), PdfInfo(8, lambda: ("a",) * 8), lambda: 1000.0)
    run_select(tui, deck_pdf)
    assert terminal.exited is True
    assert state.load(deck_pdf)["view"] == 2


@needs_poppler
@pytest.mark.integration
def test_make_tui_restores_the_saved_page_and_puts_the_projector_there(deck_pdf: Path) -> None:
    state.save(deck_pdf, {"page": 3})
    pages: list[int] = []

    class Recorder(NullProjector):
        def goto(self, page: int) -> None:
            pages.append(page)

    notes = deck_pdf.parent / "notes.md"
    notes.write_text("<!-- slide: 1 -->\nhello\n")
    tui = make_tui(deck_pdf, notes, Options(), Recorder())
    assert tui.deck.view == 3
    assert pages == [3]
    assert tui._sections


@needs_poppler
@pytest.mark.integration
def test_pdf_info_offers_previews_only_when_the_tools_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdftools, "previews_available", lambda: False)
    plain = pdf_info(EXAMPLES / "slides.pdf")
    assert (plain.pages, plain.preview) == (8, None)
    assert "lectos" in plain.texts()[0]
    monkeypatch.setattr(pdftools, "previews_available", lambda: True)
    monkeypatch.setattr(pdftools, "preview", lambda pdf, page, cols, rows: [f"{page}:{cols}x{rows}"])
    rich = pdf_info(EXAMPLES / "slides.pdf")
    assert rich.preview is not None
    assert rich.preview(2, 30, 5) == ["2:30x5"]
