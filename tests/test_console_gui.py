"""GUI wiring checks for the GTK console. They need a display and GTK, so they are skipped elsewhere."""

from pathlib import Path

import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, Gio, Gtk  # noqa: E402

from lectos import commands, config, header  # noqa: E402

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(Gdk.Display.get_default() is None, reason="needs a display"),
]

ROOT = Path(__file__).parent.parent / "examples"


@pytest.fixture(scope="module")
def console(tmp_path_factory: pytest.TempPathFactory):
    from lectos.app import build_core
    from lectos.console import ConsoleWindow
    from lectos.projection import GTK_CAPS, NullProjector

    mp = pytest.MonkeyPatch()
    mp.setenv("XDG_STATE_HOME", str(tmp_path_factory.mktemp("state")))  # never read the presenter's real saved state
    mp.setenv("XDG_CACHE_HOME", str(tmp_path_factory.mktemp("cache")))
    options = config.Options()
    app = Adw.Application(application_id="org.lectos.test", flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.register()
    core = build_core(ROOT / "slides.pdf", GTK_CAPS, options)

    class Projector(NullProjector):
        caps = GTK_CAPS

    window = ConsoleWindow(app, core.stage, doc=core.doc, projector=Projector(), notes=None, options=options)
    yield window
    window.destroy()
    mp.undo()


def walk(model: Gio.MenuModel):
    """Every (label, action) leaf in a menu model, descending into sections and submenus."""
    for i in range(model.get_n_items()):
        for kind in ("section", "submenu"):
            link = model.get_item_link(i, kind)
            if link is not None:
                yield from walk(link)
        action = model.get_item_attribute_value(i, "action")
        label = model.get_item_attribute_value(i, "label")
        if action is not None:
            yield (label.get_string() if label else ""), action.get_string()


def test_every_menu_entry_points_at_a_registered_action(console) -> None:
    entries = list(walk(console._menu_model()))
    assert len(entries) > 40
    for label, detailed in entries:
        assert detailed.startswith("win."), label
        name = detailed.removeprefix("win.").split("::")[0]
        assert console.lookup_action(name) is not None, f"{label!r} -> {detailed}"


def test_every_console_command_is_documented(console) -> None:
    assert set(console._commands) <= set(commands.HELP)


def test_every_header_item_can_be_built(console) -> None:
    for name in header.ITEM_NAMES:
        widget = console._header_widget(name)
        assert isinstance(widget, Gtk.Widget), name


def test_banners_show_frozen_blackout_and_board(console) -> None:
    assert not any(b.get_revealed() for b in console._banners.values())
    console.execute("freeze on")
    console.execute("blackout on")
    console.execute("board on")
    assert all(b.get_revealed() for b in console._banners.values())
    assert "slide 1" in console._banners["freeze"].get_title()
    for command in ("freeze off", "blackout off", "board off"):
        console.execute(command)
    assert not any(b.get_revealed() for b in console._banners.values())


def test_tool_summary_and_commands_update_the_footer(console) -> None:
    console.execute("highlighter on")
    console.execute("color blue")
    console.execute("laser on")
    assert console.tools_label.get_label() == "highlighter blue 4, laser"
    console.execute("highlighter off")
    console.execute("laser off")
    console.execute("color nope")
    assert console.last_message.startswith("colour:")


def test_clear_all_toasts_with_undo_and_restore_brings_ink_back(console) -> None:
    console.ink.begin("s0", 1.0, 1.0, 1.0)
    console.execute("clear-all")
    assert console.last_message.startswith("erased 1 strokes")
    assert console._toast is not None
    assert console._toast.get_action_name() == "win.restore-all"
    console.lookup_action("restore-all").activate(None)
    assert len(console.ink.strokes("s0")) == 1


def test_layout_commands_and_gating(console) -> None:
    console.execute("layout wide")
    assert console.layout_active == "wide"
    console.execute("layout compact")
    assert console.layout_active == "compact"
    console.execute("upcoming 99")
    assert console.upcoming == 16
    console.execute("help")
    assert console.stack.get_visible_child_name() == "help"
    console.execute("main")
    assert console.stack.get_visible_child_name() == "main"


def test_search_panel_keeps_the_slides_visible(console) -> None:
    console.execute("main")
    console.execute("search lectos")
    assert console.search_revealer.get_reveal_child() is True
    assert console.stack.get_visible_child_name() == "main"  # the slides and notes are still there
    assert console.hits
    first = console.hits[0]
    console.execute("hit-next")
    assert console.stack.get_visible_child_name() == "main"
    assert console.search_revealer.get_reveal_child() is True  # stepping through hits keeps the panel open
    assert first.kind in ("slide", "notes")
    console.execute("search")  # no text: toggles the panel closed
    assert console.search_revealer.get_reveal_child() is False
    console.execute("search")
    assert console.search_revealer.get_reveal_child() is True
    console.execute("main")
    assert console.search_revealer.get_reveal_child() is False


def test_grid_click_looks_double_click_goes_and_cancel_restores(console) -> None:
    deck = console.deck
    console.execute("main")
    console.execute("goto 2")
    start, projected = deck.view, deck.page
    console.execute("overview")
    assert console.stack.get_visible_child_name() == "overview"
    console.flow.select_child(console.flow.get_child_at_index(5))  # a single click
    assert (deck.view, deck.page) == (5, projected)  # looked at, projector untouched
    console.execute("overview")  # the button again: cancel
    assert console.stack.get_visible_child_name() == "main"
    assert deck.view == start  # previous condition restored
    console.execute("overview")
    child = console.flow.get_child_at_index(6)
    console.flow.select_child(child)
    console.flow.emit("child-activated", child)  # a double click
    assert console.stack.get_visible_child_name() == "main"
    assert (deck.view, deck.page) == (6, 6)
    console.execute("overview")
    console.flow.select_child(console.flow.get_child_at_index(1))
    console.execute("main")  # Escape
    assert deck.view == 6


def test_menu_is_grouped_into_submenus(console) -> None:
    model = console._menu_model()
    top_leaves, submenus = 0, []
    for i in range(model.get_n_items()):
        section = model.get_item_link(i, "section")
        for j in range(section.get_n_items()):
            if section.get_item_link(j, "submenu") is not None:
                title = section.get_item_attribute_value(j, "label").get_string()
                submenus.append(title)
            else:
                top_leaves += 1
    assert top_leaves <= 20
    assert {"Timer", "Drawing", "Laser pointer"} <= set(submenus)


def test_custom_lecture_length_from_the_command_and_menu(console) -> None:
    console.execute("target 1h45")
    assert console.timer.target_min == 105
    console.execute("target nonsense")
    assert console.last_message.startswith("target needs a length")
    console.lookup_action("target-prompt").activate(None)
    assert console.cmd.get_text() == ":target "
    console.show_main()
    console.execute("target 90")


def test_console_in_russian(tmp_path_factory: pytest.TempPathFactory) -> None:
    from lectos import i18n
    from lectos.app import build_core
    from lectos.console import ConsoleWindow
    from lectos.projection import GTK_CAPS, NullProjector

    mp = pytest.MonkeyPatch()
    mp.setenv("XDG_STATE_HOME", str(tmp_path_factory.mktemp("state-ru")))
    i18n.init("ru")
    try:
        app = Adw.Application(application_id="org.lectos.testru", flags=Gio.ApplicationFlags.NON_UNIQUE)
        app.register()
        core = build_core(ROOT / "slides.pdf", GTK_CAPS, config.Options())

        class Projector(NullProjector):
            caps = GTK_CAPS

        window = ConsoleWindow(
            app, core.stage, doc=core.doc, projector=Projector(), notes=None, options=config.Options()
        )
        model = window._menu_model()
        labels = []
        for i in range(model.get_n_items()):
            section = model.get_item_link(i, "section")
            labels += [section.get_item_attribute_value(j, "label").get_string() for j in range(section.get_n_items())]
        assert "Предыдущий слайд" in labels
        assert "Обзор" in labels
        window.execute("freeze on")
        assert "заморожен" in window._banners["freeze"].get_title()
        window.execute("nonsense")
        assert window.last_message.startswith("неизвестная команда")
        window.destroy()
    finally:
        i18n.init("en")
        mp.undo()
