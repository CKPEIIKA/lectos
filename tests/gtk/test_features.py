import shutil

import cairo
import pytest
from conftest import EXAMPLES
from gi.repository import Gtk

from lectos.gtk import console as console_module
from lectos.model import layout as layouts
from lectos.notes.markdown import NotesError


class FakeEditor:
    """Stands in for the modal editor window; remembers what it was opened with."""

    opened: list["FakeEditor"] = []  # noqa: RUF012

    def __init__(self, parent, slide: int, text: str, on_save) -> None:
        self.slide, self.text, self.on_save = slide, text, on_save
        FakeEditor.opened.append(self)

    def present(self) -> None:
        pass


@pytest.fixture
def editor(monkeypatch):
    FakeEditor.opened = []
    monkeypatch.setattr(console_module, "NotesEditor", FakeEditor)
    return FakeEditor


@pytest.fixture
def md_notes(tmp_path):
    path = tmp_path / "talk.md"
    shutil.copy(EXAMPLES / "notes.md", path)
    return path


# ---- panels ----
def test_panels_can_be_hidden_one_by_one_and_come_back(rig) -> None:
    c = rig.console
    c.execute("panel notes off")
    assert c.scroller is None
    assert c.hidden == {"notes"}
    c._scroll(3)  # no notes view: nothing to scroll
    c._scroll_to_section(0)
    c._rebuild_notes()
    assert c._restore_scroll(5.0) is False
    c.execute("panel notes")  # no value: toggles
    assert c.scroller is not None
    assert c.hidden == set()


def test_compact_layout_without_previews_is_just_the_slide_and_the_notes(rig) -> None:
    c = rig.console
    c.execute("panel audience off")
    c.execute("panel next off")
    assert c._small_row(130) is None
    assert c.main_holder.get_first_child().get_start_child().get_last_child() is c._stage_areas[0]
    c.execute("panel notes off")
    assert isinstance(c.main_holder.get_first_child(), Gtk.Box)  # no splitter without notes
    c._fit_pane()  # and nothing to fit


def test_the_wide_layout_drops_what_is_hidden(rig) -> None:
    c = rig.console
    c.execute("layout wide")
    assert c._strip_box is not None
    for name in ("strip", "audience", "next", "notes"):
        c.execute(f"panel {name} off")
    assert c._strip_box is None
    assert c.paned is None
    c.execute("panel next on")
    assert c.paned is not None


def test_the_status_bar_can_be_hidden_but_the_command_line_stays(rig) -> None:
    c = rig.console
    c.execute("panel status off")
    assert not c.pos.get_visible()
    assert not c.tools_label.get_visible()
    c._open_command()
    assert c.cmd.get_visible()
    c.execute("panel status on")
    assert c.info.get_visible()


def test_an_unknown_panel_lists_the_known_ones(rig) -> None:
    rig.console.execute("panel bogus")
    assert rig.console.last_message == "panel needs one of: notes audience next strip status"


def test_hidden_panels_are_remembered_and_unknown_names_ignored(rig, build_rig) -> None:
    from lectos import config

    rig.console.execute("panel strip off")
    saved = rig.console.snapshot()
    assert saved["hidden"] == ["strip"]
    again = build_rig(options=config.Options(hidden=("next",))).console
    assert again.hidden == {"next"}
    again.restore(saved)
    assert again.hidden == {"strip"}
    again.restore({"hidden": ["strip", "bogus"], "layout": "wide"})
    assert again.hidden == {"strip"}
    again.restore({"hidden": "nonsense"})
    assert again.hidden == {"strip"}


# ---- the drawing layout ----
def test_the_drawing_layout_lets_the_mouse_draw_and_gives_it_back(rig) -> None:
    c = rig.console
    c.execute("layout draw")
    assert c.layout_active == layouts.DRAW
    assert c.ink.tool.mouse_draw is True
    assert c._drawbar is not None
    assert c.scroller is None
    c.execute("layout wide")
    assert c.ink.tool.mouse_draw is False
    assert c._drawbar is None
    c.execute("draw on")
    c.execute("layout draw")
    c.execute("layout compact")
    assert c.ink.tool.mouse_draw is True  # it was on before


def test_sketch_switches_to_the_drawing_layout_and_back(rig, plain) -> None:
    c = rig.console
    c.execute("layout wide")
    c.execute("sketch on")
    c.execute("sketch on")  # already there
    assert c.layout_mode == "draw"
    assert c._flag("sketch") is True
    c.execute("sketch")  # toggles back to what it was
    assert c.layout_mode == "wide"
    c.execute("layout draw")
    c.execute("sketch off")  # the draw layout was chosen directly: back to what it replaced
    assert c.layout_mode == "wide"
    c.restore({"layout": "draw"})
    c.execute("sketch off")  # restored from a file: back to automatic
    assert c.layout_mode == "auto"
    plain.console.execute("sketch on")
    assert "not supported" in plain.console.last_message


def test_the_drawing_toolbar_runs_commands_and_shows_the_real_pen(rig) -> None:
    c = rig.console
    c.execute("layout draw")
    bar = c._drawbar
    bar.swatches["red"].emit("clicked")
    assert c.pen_color_name() == "red"
    assert "selected" in bar.swatches["red"].get_css_classes()
    c.execute("color blue")
    assert "selected" in bar.swatches["blue"].get_css_classes()
    assert "selected" not in bar.swatches["red"].get_css_classes()
    bar.width.set_value(12)
    assert c.pen_width() == 12
    c.execute("width 6")
    assert bar.width.get_value() == 6
    assert set(bar.buttons) == {"highlighter", "eraser", "undo", "redo", "clear", "board", "laser"}
    bar.buttons["eraser"].set_active(True)
    assert c.ink.tool.eraser is True
    assert c.target_minutes() == c.timer.target_min


# ---- notes editing ----
def test_editing_opens_the_editor_with_the_slide_s_notes(rig, plain, editor) -> None:
    c = rig.console
    c.deck.goto(2)
    c.execute("edit")
    assert (editor.opened[0].slide, "Slide 3" in editor.opened[0].text or editor.opened[0].text != "") == (3, True)
    plain.console.execute("edit")
    assert "no notes are loaded" in plain.console.last_message
    assert len(editor.opened) == 1


def test_a_slide_without_notes_starts_with_an_empty_editor(build_rig, tmp_path, editor) -> None:
    notes = tmp_path / "n.md"
    notes.write_text("<!-- slide: 1 -->\nonly the first\n")
    c = build_rig(notes=notes).console
    c.deck.goto(4)
    c.execute("edit")
    assert (editor.opened[0].slide, editor.opened[0].text) == (5, "")


def test_saved_markdown_notes_are_written_to_the_file_and_shown(build_rig, md_notes, editor) -> None:
    c = build_rig(notes=md_notes).console
    c.execute("edit")
    editor.opened[0].on_save("brand new words")
    assert "brand new words" in md_notes.read_text()
    assert "brand new words" in c.buffer.get_text(c.buffer.get_start_iter(), c.buffer.get_end_iter(), False)
    assert c.last_message == "notes of slide 1 saved"


def test_saved_beamer_notes_leave_the_tex_alone(rig, editor, tmp_path) -> None:
    c = rig.console
    tex = EXAMPLES / "slides.tex"
    before = tex.read_text()
    c.execute("edit")
    editor.opened[0].on_save("my version")
    assert tex.read_text() == before
    assert any(s.text.strip() == "my version" for s in c._sections)


def test_notes_that_cannot_be_saved_say_why(rig, editor) -> None:
    c = rig.console

    def refuse(slide: int, text: str) -> None:
        raise NotesError("read-only notes")

    c.notes.save = refuse
    c.execute("edit")
    editor.opened[0].on_save("x")
    assert c.last_message == "read-only notes"
    c.notes = None
    c._save_notes(1, "late")  # the notes went away meanwhile: nothing happens


# ---- open, settings, export ----
def test_open_runs_what_the_application_provides(rig) -> None:
    c = rig.console
    c.execute("open")
    assert "not available" in c.last_message
    called = []
    c.opener = lambda: called.append(1)
    c.execute("open")
    assert called == [1]


def test_the_settings_window_opens_once_and_follows_the_console(rig) -> None:
    c = rig.console
    c.execute("settings")
    window = c._settings
    c.execute("settings")
    assert c._settings is window
    c.execute("panel strip off")
    assert window.panel_rows["strip"].get_active() is False
    c.execute("layout wide")
    assert window.layout_row.get_selected() == 2
    assert c._settings_closed(window) is False
    assert c._settings is None
    window.destroy()


def test_the_drawing_layer_is_exported_to_a_png_that_never_overwrites(rig, tmp_path) -> None:
    c = rig.console
    c.execute("color red")
    c.ink.begin(c.stage.layer(0), 20.0, 20.0, 1.0)
    c.ink.extend(c.stage.layer(0), 100.0, 60.0, 1.0)
    c.ink.finish(c.stage.layer(0))
    target = tmp_path / "layer.png"
    c.execute(f"export-ink {target}")
    c.execute(f"export-ink {target}")
    assert target.read_bytes().startswith(b"\x89PNG")
    assert (tmp_path / "layer-2.png").exists()
    assert c.last_message.startswith("wrote ")
    c.execute(f"export-ink {tmp_path / 'missing' / 'x.png'}")
    assert c.last_message.startswith("export failed:")


def test_the_default_name_of_an_exported_layer_names_the_slide_or_board(rig, monkeypatch, tmp_path) -> None:
    c = rig.console
    written = []
    monkeypatch.setattr(c.stage, "export_ink_png", lambda path, page: written.append(path.name))
    c.deck.goto(1)
    c.execute("export-ink")
    c.execute("board on")
    c.execute("export-ink")
    assert written[0].endswith("-slide-2-ink.png")
    assert written[1].endswith("-board-ink.png")


# ---- look ----
def test_overview_tiles_keep_their_height_and_the_timer_has_room(rig) -> None:
    assert rig.console.flow.get_valign() == Gtk.Align.START
    assert "lectos-timer" in rig.console.timer_button.get_css_classes()


def test_restoring_a_drawing_layout_state_works_without_the_notes_view(rig, pump) -> None:
    c = rig.console
    c.restore({"layout": "draw", "notes_scroll": 40.0})
    pump(0.05)
    assert c.layout_active == layouts.DRAW


# ---- links, notes pages, annotations ----
SPLIT_PAGE = {"size": (800, 300), "text": "SLIDE", "text_right": "NOTES"}


def test_following_and_opening_links_from_the_console(rig, monkeypatch) -> None:
    c = rig.console
    seen = []
    monkeypatch.setattr(console_module, "launch", lambda uri: seen.append(uri) or "")
    c._open_uri("https://example.org")
    assert c.last_message == "opened https://example.org"
    monkeypatch.setattr(console_module, "launch", lambda uri: "no browser")
    c._open_uri("https://example.org")
    assert c.last_message == "link not opened: no browser"
    assert seen == ["https://example.org"]


def test_the_projector_reports_links_it_cannot_open_on_stderr(rig, application, monkeypatch, capsys) -> None:
    from lectos import config
    from lectos.gtk import projector as projector_module
    from lectos.gtk.projector import ProjectorWindow

    window = ProjectorWindow(application, rig.core.stage, rig.core.ink, None, config.Blackout())
    monkeypatch.setattr(projector_module, "launch", lambda uri: "no browser")
    window._open_uri("https://example.org")
    assert "link not opened: no browser" in capsys.readouterr().err
    monkeypatch.setattr(projector_module, "launch", lambda uri: "")
    window._open_uri("https://example.org")
    assert capsys.readouterr().err == ""
    window.destroy()


def test_notes_pages_are_shown_above_the_text_notes(build_rig, pdf_maker, tmp_path) -> None:
    pdf = pdf_maker([SPLIT_PAGE, SPLIT_PAGE])
    notes = tmp_path / "n.md"
    notes.write_text("<!-- slide: 1 -->\nsome text\n")
    c = build_rig(pdf=pdf, notes=notes).console
    holder = c.main_holder.get_first_child()
    pane = holder.get_end_child()
    assert isinstance(pane, Gtk.Box)
    assert isinstance(pane.get_first_child(), Gtk.AspectFrame)
    assert c.scroller is not None
    area = pane.get_first_child().get_child()
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 100)
    c._draw_notes_page(cairo.Context(surface), 200, 100)
    surface.flush()
    assert any(bytes(surface.get_data()))
    c.deck.view = 9  # out of range: nothing is drawn, nothing breaks
    c._draw_notes_page(cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 20, 20)), 20, 20)
    assert area in c._plain_areas


def test_notes_pages_alone_need_no_text_view(build_rig, pdf_maker) -> None:
    c = build_rig(pdf=pdf_maker([SPLIT_PAGE]), notes=False).console
    assert c.scroller is None
    assert isinstance(c.main_holder.get_first_child().get_end_child(), Gtk.AspectFrame)


def test_notes_pages_follow_the_options(build_rig, pdf_maker) -> None:
    from lectos import config

    c = build_rig(pdf=pdf_maker([SPLIT_PAGE]), notes=False, options=config.Options(notes_pages="none")).console
    assert c.doc.notes_side == ""
    assert c.doc.page_size(0) == (800, 300)


def test_the_launcher_uses_pdf_annotations_as_notes_and_warns_about_zathura(
    application, pdf_maker, monkeypatch
) -> None:
    from lectos import config
    from lectos.gtk import app as app_module
    from lectos.gtk.pdfdoc import AnnotationNotes
    from lectos.projectors.projection import NullProjector

    annotated = pdf_maker([{"notes": [((10, 10, 30, 30), "say this")]}], name="a.pdf")

    def current(launcher):
        assert launcher.session is not None
        return launcher.session

    launcher = app_module.Launcher(application, config.Options(), projector="none", windowed=True, monitor=None)
    launcher.begin(annotated, None)
    assert isinstance(current(launcher).console.notes, AnnotationNotes)
    current(launcher).finish()
    plain = pdf_maker([{}], name="p.pdf")
    launcher.begin(plain, None)
    assert current(launcher).console.notes is None
    current(launcher).finish()
    monkeypatch.setattr(app_module, "make_projector", lambda *a, **k: NullProjector())
    zathura = app_module.Launcher(application, config.Options(), projector="zathura", windowed=True, monitor=None)
    zathura.begin(pdf_maker([SPLIT_PAGE], name="s.pdf"), None)
    assert "notes pages" in current(zathura).console.last_message
    current(zathura).finish()
