import pytest
from gi.repository import Gdk

from lectos.gtk.widgets.notesedit import NotesEditor
from lectos.gtk.widgets.settings import LAYOUT_TITLES, SettingsWindow

NONE = Gdk.ModifierType(0)


@pytest.fixture
def settings(rig):
    window = SettingsWindow(rig.console, rig.console)
    yield window, rig.console
    window.destroy()


def test_the_rows_show_the_real_state(settings) -> None:
    window, c = settings
    assert all(row.get_active() for row in window.panel_rows.values())
    assert window.layout_row.get_selected() == 0
    assert window.previous_row.get_value() == c.previous
    assert window.upcoming_row.get_value() == c.upcoming
    assert window.target_row.get_value() == c.timer.target_min
    assert window.behaviour_rows["vim"].get_active() is True


def test_changing_a_row_runs_the_command(settings) -> None:
    window, c = settings
    window.panel_rows["notes"].set_active(False)
    assert "notes" in c.hidden
    window.panel_rows["notes"].set_active(True)
    assert "notes" not in c.hidden
    window.layout_row.set_selected([m for m, _ in LAYOUT_TITLES].index("wide"))
    assert c.layout_mode == "wide"
    window.previous_row.set_value(1)
    window.upcoming_row.set_value(5)
    window.target_row.set_value(75)
    assert (c.previous, c.upcoming, c.timer.target_min) == (1, 5, 75)
    window.behaviour_rows["vim"].set_active(False)
    window.behaviour_rows["show-slide"].set_active(False)
    assert (c.vim_on, c.show_slide_on) == (False, False)


def test_syncing_never_sends_commands_back(settings) -> None:
    window, c = settings
    c.hidden.add("strip")  # changed behind the window's back
    window.sync()
    assert window.panel_rows["strip"].get_active() is False
    assert c.hidden == {"strip"}


@pytest.fixture
def editor(rig):
    saved: list[str] = []
    window = NotesEditor(rig.console, 4, "first words", saved.append)
    yield window, saved
    window.destroy()


def test_the_editor_hands_over_the_edited_text(editor) -> None:
    window, saved = editor
    assert window.text() == "first words"
    window.view.get_buffer().set_text("changed")
    window.save()
    assert saved == ["changed"]


def test_escape_discards_and_ctrl_enter_saves(editor) -> None:
    window, saved = editor
    assert window._on_key(None, Gdk.KEY_Escape, 0, NONE) is True
    assert saved == []
    assert window._on_key(None, Gdk.KEY_Return, 0, NONE) is False  # a plain Enter is a new line
    assert window._on_key(None, Gdk.KEY_Return, 0, Gdk.ModifierType.CONTROL_MASK) is True
    assert saved == ["first words"]
