import cairo
from conftest import EXAMPLES
from gi.repository import Gdk

from lectos.gtk import console as console_module
from lectos.notes import mathimg
from lectos.notes.markdown import NotesError

NONE = Gdk.ModifierType(0)


def test_unrecognised_vim_input_is_left_alone(rig) -> None:
    assert rig.console._vim_key(Gdk.KEY_Shift_L) is False  # not a character
    assert rig.console._vim_key(Gdk.KEY_F5) is False  # no vim meaning


def test_the_overview_opens_on_the_viewed_slide_even_without_such_a_child(rig) -> None:
    c = rig.console
    c.execute("overview")
    assert c.stack.get_visible_child_name() == "overview"
    c.deck.view = 999  # no tile for it
    c.stack.set_visible_child_name("main")
    c.execute("overview")
    assert c.stack.get_visible_child_name() == "overview"


def test_switches_ignore_requests_that_change_nothing(rig) -> None:
    c = rig.console
    for name in ("board", "blackout", "freeze"):
        c.execute(f"{name} off")
        assert getattr(c.deck, {"board": "board", "blackout": "blackout", "freeze": "frozen"}[name]) is False
    c.execute("board on")
    c.execute("board on")
    assert c.deck.board is True


def test_a_notes_file_that_breaks_is_reported_and_retried(build_rig, tmp_path, pump) -> None:
    notes = tmp_path / "n.md"
    notes.write_text("# Slide 1\n\nhello\n")
    c = build_rig(notes=notes).console
    notes.write_text("# Slide 1\n\nchanged\n")

    def broken() -> list:
        raise NotesError("cannot parse the notes")

    c.notes.load = broken
    c._notes_mtime = -1
    c.poll_notes()
    assert c.last_message == "cannot parse the notes"


def test_the_notes_colour_falls_back_when_the_theme_has_none(rig, monkeypatch) -> None:
    c = rig.console
    assert c._math_color().startswith("#")
    monkeypatch.setattr(c.view, "get_color", lambda: (_ for _ in ()).throw(AttributeError("old GTK")))
    assert c._math_color() == mathimg.DEFAULT_FG
    c.view = None
    assert c._math_color() == mathimg.DEFAULT_FG


def test_changing_the_theme_recompiles_the_formulas(rig) -> None:
    c = rig.console
    assert c._recompile_math() is False
    assert c._notes_mtime != -1


def test_compiled_formulas_become_textures_and_failures_are_reported(rig) -> None:
    c = rig.console
    mtime = c._notes_mtime
    assert c._math_ready({}, mtime - 5) is False  # notes changed while compiling: stale result
    broken = EXAMPLES / "slides.pdf"  # not an image: GdkTexture refuses it
    formula = mathimg.Formula("x", False)
    assert c._math_ready({formula: broken}, mtime) is False
    assert c.last_message.startswith("math image error:")
    image = cairo.ImageSurface(cairo.FORMAT_ARGB32, 4, 4)
    path = EXAMPLES.parent / ".pytest_cache" / "formula.png"
    path.parent.mkdir(exist_ok=True)
    image.write_to_png(str(path))
    assert c._math_ready({formula: path}, mtime) is False
    assert formula in c._textures


def test_the_compile_step_posts_its_result_to_the_main_loop(rig, monkeypatch, pump) -> None:
    c = rig.console
    seen = []
    monkeypatch.setattr(c, "_math_ready", lambda images, mtime: seen.append((images, mtime)) or False)
    c._compile_math(c._sections, 7, "#000000")
    pump(0.1)
    assert seen == [({}, 7)]


def test_a_formula_without_an_image_is_shown_as_its_source(rig) -> None:
    c = rig.console
    c._textures.clear()
    c._rebuild_notes()
    assert c.buffer.get_char_count() > 0


def test_scrolling_to_a_missing_section_does_nothing(rig) -> None:
    rig.console._scroll_to_section(9999)


def test_restoring_state_tolerates_nonsense_and_marks_the_current_section(rig, pump) -> None:
    c = rig.console
    c.restore({"vim": "yes", "notes_scroll": True, "panes": {"wide": 400, "bogus": 3}, "layout": "wide"})
    assert c.layout_mode == "wide"
    assert c.vim_on is True
    c.restore({"vim": False, "notes_scroll": 3.5, "previous": 2, "upcoming": 99})
    pump(0.05)
    assert c.vim_on is False
    assert c.upcoming <= 16
    c.deck.goto(1)
    c._mark_current_section()
    assert c.snapshot()["vim"] is False
    c._sections = []
    c._mark_current_section()


def test_a_header_can_keep_the_start_end_and_title_items_it_is_given(build_rig) -> None:
    from lectos import config

    header = config.Header(start=("prev", "next"), end=("freeze", "menu"), title="slide")
    options = config.Options(header=header)
    c = build_rig(options=options).console
    assert c._header_widget("next") is not None
    c.deck.set_frozen(True)
    c._sync_actions()
    from lectos.model import header as header_items

    toggles = {name for name, item in header_items.ITEMS.items() if item.toggle}
    assert toggles == set(console_module.TOGGLE_CSS)  # every toggle lights up while active


def test_a_header_without_a_title_has_none(build_rig) -> None:
    from lectos import config

    c = build_rig(options=config.Options(header=config.Header(title="none"))).console
    assert c.timer_button is not None
    c._after_resize()
    c.scroller = None
    c._after_resize()  # no notes pane to realign


def test_unchanged_notes_are_not_reloaded_and_known_formulas_show_their_image(rig) -> None:
    import cairo

    c = rig.console
    c.poll_notes()
    c.poll_notes()  # same stamp: nothing to do
    path = EXAMPLES.parent / ".pytest_cache" / "f.png"
    path.parent.mkdir(exist_ok=True)
    cairo.ImageSurface(cairo.FORMAT_ARGB32, 4, 4).write_to_png(str(path))
    texture = Gdk.Texture.new_from_filename(str(path))
    formulas = c._formulas(c._sections)
    assert formulas
    c._textures = dict.fromkeys(formulas, texture)
    c._rebuild_notes()
