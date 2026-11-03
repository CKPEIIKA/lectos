import shutil
from pathlib import Path

import pytest
from gi.repository import Gdk, Gio, GLib, Gtk

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


def test_a_pdf_picked_in_the_folder_dialog_is_taken_as_the_slides(started, deck) -> None:
    window, _calls = started
    assert window.set_folder(deck / "slides.pdf") is True
    assert (window.slides, window.notes) == (deck / "slides.pdf", deck / "slides.tex")
    assert window.set_folder(deck / "notes.md") is False  # another kind of file is no folder either


def test_a_drop_selects_slides_notes_or_a_folder_and_rejects_ambiguous_files(started, deck, tmp_path) -> None:
    window, _calls = started
    pdf, tex, md = deck / "slides.pdf", deck / "slides.tex", deck / "notes.md"
    assert window._apply_drop([]) is False
    assert window._apply_drop([deck]) is True
    assert (window.slides, window.notes) == (pdf, tex)

    empty = tmp_path / "empty"
    empty.mkdir()
    assert window._apply_drop([empty]) is False
    assert window._apply_drop([pdf, md]) is True
    assert (window.slides, window.notes) == (pdf, md)
    assert window._apply_drop([md]) is True
    assert window._apply_drop([pdf]) is True
    assert window._apply_drop([pdf, pdf]) is False
    assert window._apply_drop([md, tex]) is False
    other = tmp_path / "other.txt"
    other.write_text("text")
    assert window._apply_drop([pdf, other]) is False


def test_drop_paths_accept_only_bounded_local_file_lists(started, deck) -> None:
    window, _calls = started
    files = [Gio.File.new_for_path(str(deck / name)) for name in ("slides.pdf", "slides.tex", "notes.md")]
    assert window._drop_paths(object()) is None
    assert window._drop_paths(Gdk.FileList.new_from_array(files)) is None
    assert window._drop_paths(Gdk.FileList.new_from_array([Gio.File.new_for_uri("https://example.test/a.pdf")])) is None
    assert window._drop_paths(Gdk.FileList.new_from_array(files[:2])) == [deck / "slides.pdf", deck / "slides.tex"]


def test_drop_callback_routes_only_valid_local_file_lists(started, deck, monkeypatch) -> None:
    window, _calls = started
    received = []

    def apply(paths):
        received.append(paths)
        return True

    monkeypatch.setattr(window, "_apply_drop", apply)
    assert window._drop_files(None, object(), 0.0, 0.0) is False
    remote = Gdk.FileList.new_from_array([Gio.File.new_for_uri("https://example.test/a.pdf")])
    assert window._drop_files(None, remote, 0.0, 0.0) is False
    files = Gdk.FileList.new_from_array([Gio.File.new_for_path(str(deck / "slides.pdf"))])
    assert window._drop_files(None, files, 0.0, 0.0) is True
    assert received == [[deck / "slides.pdf"]]


def test_the_default_window_shows_everything_without_scrolling_and_may_shrink(started) -> None:
    window, _calls = started
    scroller = window.get_content().get_content()
    assert isinstance(scroller, Gtk.ScrolledWindow)
    _minimum, natural, _b, _l = scroller.get_child().measure(Gtk.Orientation.VERTICAL, 480)
    header = 60  # headerbar and borders, generously
    assert natural + header <= window.get_default_size()[1]
    assert scroller.get_propagate_natural_height() is False  # a small window scrolls instead of growing
    assert scroller.get_policy()[0] == Gtk.PolicyType.NEVER


def test_the_chooser_opens_next_to_the_chosen_files_else_where_it_last_picked(started, deck, tmp_path) -> None:
    window, _calls = started
    assert window._dialog("x").get_initial_folder() is None
    window._picked(FakeDialog(str(deck / "slides.pdf")), "result", window.set_slides)
    window.slides = window.notes = None
    assert window._start_folder() == deck  # remembered from the pick
    assert window._dialog("x").get_initial_folder().get_path() == str(deck)
    window.set_slides(tmp_path / "elsewhere" / "a.pdf")
    assert window._dialog("x").get_initial_folder().get_path() == str(tmp_path / "elsewhere")
    window.slides = None
    window.notes = None
    window._picked(FakeDialog(str(deck)), "result", window.set_folder)
    assert window._start_folder() == deck  # a picked folder is remembered itself
