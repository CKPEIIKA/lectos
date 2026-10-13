import shutil
from pathlib import Path

import pytest
from gi.repository import GLib, Gtk

from lectos.gtk.widgets.start import StartWindow

EXAMPLES = Path(__file__).resolve().parents[3] / "examples"


class Picked:
    def __init__(self, path: str | None) -> None:
        self.path = path

    def get_path(self) -> str | None:
        return self.path


class FakeDialog:
    """Answers a file dialog at once with ``answer`` (a path, None for a dialog without a path, or an error)."""

    def __init__(self, answer: str | Exception | None) -> None:
        self.answer = answer
        self.asked: list[str] = []

    def _ask(self, kind: str, callback, data) -> None:
        self.asked.append(kind)
        callback(self, "result", data)

    def open(self, _parent, _cancel, callback, data) -> None:
        self._ask("open", callback, data)

    def select_folder(self, _parent, _cancel, callback, data) -> None:
        self._ask("folder", callback, data)

    def _finish(self, _result: object) -> Picked:
        if isinstance(self.answer, Exception):
            raise self.answer
        return Picked(self.answer)

    open_finish = select_folder_finish = _finish


@pytest.fixture
def started(application):
    calls: list[tuple[Path, Path | None]] = []
    window = StartWindow(application, lambda pdf, notes: calls.append((pdf, notes)))
    yield window, calls
    window.destroy()


@pytest.fixture
def deck(tmp_path):
    for name in ("slides.pdf", "slides.tex", "notes.md"):
        shutil.copy(EXAMPLES / name, tmp_path / name)
    return tmp_path


def test_nothing_starts_before_slides_are_chosen(started) -> None:
    window, calls = started
    assert window.start_button.get_sensitive() is False
    window.start()
    assert calls == []


def test_choosing_slides_finds_the_notes_next_to_them(started, deck) -> None:
    window, calls = started
    window.set_slides(deck / "slides.pdf")
    assert window.start_button.get_sensitive() is True
    assert window.notes == deck / "slides.tex"
    assert "found next to the slides" in window.notes_row.get_subtitle()
    window.start()
    assert calls == [(deck / "slides.pdf", deck / "slides.tex")]


def test_chosen_notes_win_over_found_ones_and_can_be_dropped(started, deck) -> None:
    window, _calls = started
    window.set_notes(deck / "notes.md")
    window.set_slides(deck / "slides.pdf")
    assert window.notes == deck / "notes.md"
    assert "found next" not in window.notes_row.get_subtitle()
    window.set_notes(None)
    assert window.notes_row.get_subtitle() == "none (optional)"


def test_a_folder_gives_both(started, deck, tmp_path) -> None:
    window, _calls = started
    assert window.set_folder(deck) is True
    assert (window.slides, window.notes) == (deck / "slides.pdf", deck / "slides.tex")
    empty = tmp_path / "empty"
    empty.mkdir()
    assert window.set_folder(empty) is False
    assert "no PDF in" in window.slides_row.get_subtitle()


def test_the_file_dialogs_hand_their_choice_over(started, deck, monkeypatch) -> None:
    window, _calls = started
    for method, answer, check in (
        (window.choose_slides, str(deck / "slides.pdf"), lambda: window.slides == deck / "slides.pdf"),
        (window.choose_notes, str(deck / "notes.md"), lambda: window.notes == deck / "notes.md"),
        (window.choose_folder, str(deck), lambda: window.slides == deck / "slides.pdf"),
    ):
        monkeypatch.setattr(window, "_dialog", lambda *_a, answer=answer: FakeDialog(answer))
        window.slides = window.notes = None
        method()
        assert check()


def test_a_cancelled_dialog_or_one_without_a_path_changes_nothing(started, monkeypatch) -> None:
    window, _calls = started
    for answer in (GLib.Error("dismissed"), None):
        monkeypatch.setattr(window, "_dialog", lambda *_a, answer=answer: FakeDialog(answer))
        window.choose_slides()
        window.choose_folder()
    assert window.slides is None


def test_dialogs_filter_by_file_type(started) -> None:
    window, _calls = started
    assert isinstance(window._dialog("t", ("*.pdf", "*.md")), Gtk.FileDialog)
    assert window._dialog("t").get_filters() is None
