import cairo
import pytest
from gi.repository import Gdk, Gtk

NONE = Gdk.ModifierType(0)
NOTES_MD = None  # set per test from the examples folder


def canvas(width: int = 200, height: int = 120) -> tuple[cairo.ImageSurface, cairo.Context]:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    return surface, cairo.Context(surface)


def has_ink(surface: cairo.ImageSurface) -> bool:
    surface.flush()
    return any(byte for byte in surface.get_data())


def key(console, keyval: int, state: Gdk.ModifierType = NONE) -> bool:
    return console._on_key(None, keyval, 0, state)


# ---- window size, layout, panes, filmstrip ----
def test_resizing_is_debounced_and_then_applied(rig, pump) -> None:
    c = rig.console
    c._on_resized()
    c._on_resized()  # a second event while one is pending changes nothing
    assert c._resize_pending is True
    pump(0.4)
    assert c._resize_pending is False
    c._after_resize()  # also callable directly: layout, pane, strip and notes realignment


def test_the_footer_summary_names_every_active_tool(rig, plain) -> None:
    c = rig.console
    c.deck.board = True
    c.deck.set_laser_on(True)
    c.ink.tool.eraser = c.ink.tool.mouse_draw = c.ink.tool.highlighter = True
    text = c._tool_summary()
    assert all(part in text for part in ("highlighter", "eraser", "mouse draws", "laser", "board: chalk"))
    assert plain.console._tool_summary() == ""  # no ink without a capable projector


def test_unsupported_features_are_disabled_in_the_header_and_the_menu(plain) -> None:
    c = plain.console
    button = c._header_widget("board")
    assert button.get_sensitive() is False
    assert "not supported by this projector" in button.get_tooltip_text()
    assert c.lookup_action("board").get_enabled() is False
    assert c.lookup_action("freeze").get_enabled() is True


def test_a_toggle_button_runs_its_command_but_not_while_syncing(rig) -> None:
    c = rig.console
    c._toggled("freeze", True)
    assert c.deck.frozen is True
    c._toggled("freeze", False)
    assert c.deck.frozen is False
    c._syncing = True
    c._toggled("freeze", True)
    assert c.deck.frozen is False


def test_previews_draw_slides_and_skip_missing_pages(rig) -> None:
    c = rig.console
    for staged in (True, False):
        surface, cr = canvas()
        c._draw_page(cr, 0, 200, 120, staged)
        assert has_ink(surface)
    surface, cr = canvas()
    c._draw_page(cr, 99, 200, 120)
    assert not has_ink(surface)


def test_the_laser_follows_the_pointer_over_the_slide_only(rig) -> None:
    c = rig.console
    area = Gtk.DrawingArea()
    area.get_width = lambda: 400
    area.get_height = lambda: 400
    c._laser_motion(area, 200.0, 200.0)
    assert c.deck.laser is None  # the laser is off
    c.deck.set_laser_on(True)
    c._laser_motion(area, 200.0, 200.0)
    assert c.deck.laser == pytest.approx((0.5, 0.5), abs=0.02)
    c._laser_motion(area, 200.0, 5.0)  # in the letterbox above the slide
    assert c.deck.laser is None


def test_only_a_user_drag_counts_as_a_chosen_pane_split(rig) -> None:
    c = rig.console
    paned = Gtk.Paned()
    paned.set_position(321)
    c._remember_pane(paned)
    assert c._pane[c.layout_active] == 321
    c._fitting = True
    paned.set_position(111)
    c._remember_pane(paned)
    assert c._pane[c.layout_active] == 321


def test_the_layout_is_rebuilt_only_when_it_changes(rig) -> None:
    c = rig.console
    c.layout_mode = "wide"
    c._apply_layout()
    assert c.layout_active == "wide"
    assert c._strip_box is not None
    child = c.main_holder.get_first_child()
    c._apply_layout()
    assert c.main_holder.get_first_child() is child


def test_the_wide_layout_gives_the_slide_most_of_the_width_until_the_user_drags(rig) -> None:
    c = rig.console
    c.layout_mode = "wide"
    c._apply_layout()
    c._pane.pop("wide", None)
    c.get_width = lambda: 1500
    c._fit_pane()
    assert c.paned.get_position() == pytest.approx(870, abs=2)
    c._pane["wide"] = 500  # the user chose a split
    c.paned.set_position(100)
    c._fit_pane()
    assert c.paned.get_position() == 100
    c.layout_mode = "compact"
    c._apply_layout()
    c._fit_pane()  # not the wide layout: nothing to fit


def test_after_a_layout_change_the_notes_realign_to_the_current_slide(rig, plain) -> None:
    c = rig.console
    c.deck.goto(3)
    assert c._after_layout(0.0) is False
    assert c._current_section() is not None
    c.scroller = None
    assert c._after_layout(0.0) is False  # nothing to scroll
    p = plain.console  # without notes there is no section: the old offset is restored
    p.scroller.get_vadjustment().set_upper(500)
    assert p._current_section() is None
    p._after_layout(0.0)


def test_the_filmstrip_follows_the_view_and_thumbnails_mark_view_and_live_slides(rig) -> None:
    c = rig.console
    c.layout_mode = "wide"
    c._apply_layout()
    first = c._strip_box.get_first_child()
    c.deck.goto(5)
    assert c._strip_box.get_first_child() is not first  # rebuilt around the new view
    c.deck.set_frozen(True)
    c.deck.goto(2)  # the viewed slide and the projected one now differ
    for page in (c.deck.view, c.deck.page, 7):
        surface, cr = canvas(160, 90)
        c._draw_thumb(cr, page, 160, 90)
        assert has_ink(surface)
    c.layout_mode = "compact"
    c._apply_layout()
    c._refresh_strip()  # no strip in the compact layout: nothing to do


# ---- header entry, timer, fullscreen ----
def test_the_goto_box_jumps_and_clears_itself(rig) -> None:
    c = rig.console
    entry = Gtk.Entry()
    entry.set_text("3")
    c._goto_entry(entry)
    assert (c.deck.view, entry.get_text()) == (2, "")
    entry.set_text("not a number")
    c._goto_entry(entry)
    assert c.deck.view == 2


def test_the_timer_button_starts_pauses_and_resets(rig) -> None:
    c = rig.console
    c._toggle_timer()
    assert c.timer.running is True
    c._tick()
    assert "accent" in c.timer_label.get_css_classes()
    assert c.timer_icon.get_icon_name() == "media-playback-pause-symbolic"
    c._reset_timer()
    assert c.timer.running is False
    assert "accent" not in c.timer_label.get_css_classes()
    assert c.timer_label.get_label().startswith("0:00 / ")
    assert c.info.get_label().startswith("ends ")


def test_console_fullscreen_can_be_requested_both_ways(rig) -> None:
    rig.console._set_console_fullscreen(True)
    rig.console._set_console_fullscreen(False)


# ---- search, help, hits ----
def test_search_results_name_their_kind_and_no_hits_say_so(build_rig, tmp_path) -> None:
    from conftest import EXAMPLES  # the examples folder

    c = build_rig(caps=True, notes=EXAMPLES / "notes.md").console
    entry = c.search_entry
    for text, title in (
        ("lectos", "Slide 1"),
        ("Markdown version", "Notes"),
        ("display equation", "Notes (slide 3)"),
    ):
        entry.set_text(text)
        c._run_search(entry)
        row = c.results.get_row_at_index(0)
        assert title in {r.get_title() for r in (c.results.get_row_at_index(i) for i in range(len(c.hits)))}, text
        assert row is not None
    entry.set_text("zzzzzzzzzz")
    c._run_search(entry)
    assert c.results.get_row_at_index(0).get_title() == "No matches"


def test_the_help_page_can_be_rebuilt_and_starts_typing_a_command(rig) -> None:
    c = rig.console
    c.show_help()
    c.show_help()  # the second call replaces the first page
    assert c.stack.get_visible_child_name() == "help"
    c._help_pick("goto")
    assert c.stack.get_visible_child_name() == "main"
    assert c.cmd.get_text() == ":goto "


def test_picking_hits_moves_the_view_or_scrolls_the_notes(rig) -> None:
    c = rig.console
    c.hits = []
    c.show_hit(0)  # nothing to show
    c.execute("search carbuncle")
    c.execute("search lectos")
    assert c.hits
    c._pick_hit(99)  # out of range: ignored
    c._pick_hit(0)
    c.execute("search instability")
    c.hits = [h for h in c.hits if h.kind == "slide"] or c.hits
    c.show_hit(len(c.hits) + 2)  # wraps around


def test_a_note_hit_previews_its_slide_without_moving_the_projector(rig) -> None:
    c = rig.console
    c.execute("search Roe")
    note_hit = next(i for i, h in enumerate(c.hits) if h.kind == "notes" and h.slide)
    page = c.deck.page
    c.show_hit(note_hit)
    assert c.deck.view == c.hits[note_hit].slide - 1
    assert c.deck.page == page
    c.show_slide_on = False
    c.deck.peek(0)
    c.show_hit(note_hit)
    assert c.deck.view == 0  # the preference says: do not follow


# ---- commands, entry, keys ----
@pytest.mark.parametrize(
    ("command", "message"),
    [
        ("layout bogus", "layout: auto, compact, wide or toggle"),
        ("upcoming x", "upcoming needs a number 0..16"),
        ("previous x", "previous needs a number 0..8"),
        ("goto x", "goto needs a slide number"),
        ("target x", "target needs a length"),
        ("nonsense", "unknown command: nonsense"),
    ],
)
def test_bad_command_arguments_say_what_was_expected(rig, command: str, message: str) -> None:
    rig.console.execute(command)
    assert rig.console.last_message.startswith(message)


def test_layout_toggle_and_counts(rig) -> None:
    c = rig.console
    c.execute("layout toggle")
    assert (c.layout_mode, c.layout_active) == ("wide", "wide")
    c.execute("layout toggle")
    assert c.layout_active == "compact"
    c.execute("upcoming 3")
    c.execute("previous 1")
    assert (c.upcoming, c.previous) == (3, 1)


def test_preferences_and_layers(rig) -> None:
    c = rig.console
    c._set_pref("vim_on", False)
    assert c.vim_on is False
    assert c._view_layer() == "s0"
    c.execute("board on")
    assert c._view_layer() == "board"


def test_drawing_flags_announce_themselves(rig) -> None:
    c = rig.console
    c.execute("draw on")
    assert c.last_message == "mouse drawing on"
    c.execute("eraser on")
    assert c.last_message == "eraser on"
    c.execute("eraser off")
    assert c.last_message == "eraser off"


def test_export_writes_a_pdf_and_reports_failures(rig, tmp_path) -> None:
    c = rig.console
    target = tmp_path / "out.pdf"
    c.execute(f"export {target}")
    assert target.read_bytes().startswith(b"%PDF-")
    assert c.last_message.startswith("wrote ")
    c.execute(f"export {tmp_path / 'missing-dir' / 'out.pdf'}")
    assert c.last_message.startswith("export failed:")


def test_help_for_one_command_and_the_full_page(rig) -> None:
    c = rig.console
    c.execute("help freeze")
    assert c.last_message.startswith("freeze [on|off]:")
    c.execute("help")
    assert c.stack.get_visible_child_name() == "help"


def test_the_command_line_runs_and_completes_with_tab(rig) -> None:
    c = rig.console
    c.cmd.set_text(":nex")
    assert c._cmd_key(None, Gdk.KEY_Tab, 0, NONE) is True
    assert c.cmd.get_text() == ":next "
    c.cmd.set_text(":f")
    c._cmd_key(None, Gdk.KEY_ISO_Left_Tab, 0, NONE)
    assert "first" in c.last_message  # several candidates are listed
    assert c._cmd_key(None, Gdk.KEY_a, 0, NONE) is False
    c.cmd.set_text(":next")
    c._run_command(c.cmd)
    assert c.deck.view == 1
    assert c.cmd.get_visible() is False
    c.say("hello")
    assert c.last_message == "hello"


def test_keys_navigate_and_vim_keys_can_be_switched_off(rig) -> None:
    c = rig.console
    for keyval, view in (
        (Gdk.KEY_Right, 1),
        (Gdk.KEY_Left, 0),
        (Gdk.KEY_End, 7),
        (Gdk.KEY_Home, 0),
        (Gdk.KEY_space, 1),
    ):
        assert key(c, keyval) is True
        assert c.deck.view == view
    assert key(c, Gdk.KEY_l) is True  # vim: next
    assert c.deck.view == 2
    assert key(c, Gdk.KEY_Page_Down) is True
    assert key(c, Gdk.KEY_Page_Up) is True
    assert key(c, Gdk.KEY_l, Gdk.ModifierType.CONTROL_MASK) is False  # Ctrl shortcuts are left to GTK
    c.vim_on = False
    assert key(c, Gdk.KEY_l) is False
    c.vim_on = True


def test_vim_prefixes_and_the_command_prompt(rig) -> None:
    c = rig.console
    assert key(c, Gdk.KEY_3) is True  # a count is pending
    assert key(c, Gdk.KEY_l) is True
    assert c.deck.view == 3
    assert key(c, Gdk.KEY_g) is True
    assert key(c, Gdk.KEY_g) is True  # gg: first slide
    assert c.deck.view == 0
    assert key(c, Gdk.KEY_colon) is True
    assert c.cmd.get_visible() is True
    assert key(c, Gdk.KEY_Shift_L) is False  # not a character: not consumed
    assert key(c, Gdk.KEY_Escape) is True
    assert c.cmd.get_visible() is False
    c.get_focus = lambda: Gtk.Entry()  # typing in an entry: keys are not intercepted
    assert key(c, Gdk.KEY_l) is False


def test_scrolling_the_notes_stays_inside_the_document(rig) -> None:
    c = rig.console
    adjustment = c.scroller.get_vadjustment()
    c._scroll(2)
    c._scroll(-10_000)
    assert adjustment.get_value() == adjustment.get_lower()
