from pathlib import Path

import pytest

from lectos import commands
from lectos.config import Options
from lectos.deck import Deck
from lectos.ink import Ink
from lectos.notes import MarkdownNotes
from lectos.projection import GTK_CAPS, NullProjector
from lectos.stage import Stage
from lectos.tui import PdfInfo, Tui
from lectos.tuitext import visible_len

PAGES = 6
NOTES = "intro\n<!-- slide: 2 -->\n## Two\nThe carbuncle instability\n<!-- slide: 4 -->\n## Four\nmore text\n"
TEXTS = tuple(f"Title {i}\nbody" for i in range(PAGES))
THIRD = 3


class FakeProjector:
    def __init__(self, caps: frozenset[str] = frozenset()) -> None:
        self.caps = caps
        self.gotos: list[int] = []
        self.full = False

    def goto(self, page: int) -> None:
        self.gotos.append(page)

    def fullscreen(self, on: bool) -> None:
        self.full = on

    def is_fullscreen(self) -> bool:
        return self.full

    def stop(self) -> None: ...


class FakeClock:
    now = 1000.0

    def __call__(self) -> float:
        return self.now


def make(tmp_path: Path, caps: frozenset[str] = frozenset(), *, with_ink: bool = False, preview: bool = False):
    notes = tmp_path / "n.md"
    notes.write_text(NOTES)
    projector = FakeProjector(caps)
    lines = ["PREVIEW"] * 3
    pdf = PdfInfo(PAGES, lambda: TEXTS, (lambda p, c, r: lines) if preview else None)
    deck = Deck(PAGES)
    ink = Ink() if with_ink else None
    stage = Stage(_Doc(), deck, ink) if ink else None
    clock = FakeClock()
    tui = Tui(MarkdownNotes(notes), Options(), projector, pdf, clock, deck=deck, ink=ink, stage=stage)
    tui.project_now()  # the startup send, so tests see only what the keys cause
    projector.gotos.clear()
    return tui, projector, clock


class _Doc:
    def page_size(self, page: int) -> tuple[float, float]:
        return 400.0, 300.0

    def paint(self, cr, page: int) -> None: ...

    def draw(self, cr, page: int, width: int, height: int):
        return 1.0, 0.0, 0.0


def keys(tui: Tui, text: str) -> None:
    for key in text.split():
        tui.handle_key(" " if key == "SP" else key)


def type_line(tui: Tui, line: str) -> None:
    for ch in line:
        tui.handle_key(ch)
    tui.handle_key("Enter")


def test_vim_navigation_drives_the_projector(tmp_path: Path) -> None:
    tui, proj, _ = make(tmp_path)
    keys(tui, "l l")
    assert (tui.deck.view, proj.gotos) == (2, [1, 2])
    keys(tui, "G")
    assert tui.deck.view == PAGES - 1
    keys(tui, "g g")
    assert tui.deck.view == 0
    keys(tui, "3 l")
    assert tui.deck.view == THIRD
    keys(tui, "Left Right Right")
    assert tui.deck.view == THIRD + 1


def test_colon_goto_and_quit(tmp_path: Path) -> None:
    tui, _, _ = make(tmp_path)
    keys(tui, ":")
    assert tui.mode == "command"
    type_line(tui, "5")
    assert tui.deck.view == THIRD + 1
    type_line_ = ":$"
    keys(tui, ":")
    type_line(tui, type_line_[1:])
    assert tui.deck.view == PAGES - 1
    keys(tui, ":")
    type_line(tui, "q")
    assert tui.running is False


def test_freeze_holds_projector_until_unfrozen(tmp_path: Path) -> None:
    tui, proj, _ = make(tmp_path)
    keys(tui, "z l l")
    assert (tui.deck.view, tui.deck.page, proj.gotos) == (2, 0, [])
    keys(tui, "z")
    assert proj.gotos == [2]


def test_tab_completion_in_command_line(tmp_path: Path) -> None:
    tui, _, _ = make(tmp_path)
    keys(tui, ": f r Tab")
    assert tui.buffer == ":freeze "
    tui.handle_key("Esc")
    assert tui.mode == "normal"
    keys(tui, ": f Tab")
    assert "first" in tui.message
    assert tui.buffer == ":f"


def test_commands_needing_gtk_or_the_projector_say_so(tmp_path: Path) -> None:
    tui, _, _ = make(tmp_path)
    tui.execute("laser on")
    assert "needs the GTK console" in tui.message
    tui.execute("board")
    assert tui.message == "board: not supported by this projector"
    assert tui.deck.board is False
    tui.execute("nonsense")
    assert "unknown command" in tui.message


def test_gtk_projector_enables_board_blackout_and_ink(tmp_path: Path) -> None:
    tui, _, _ = make(tmp_path, GTK_CAPS - {"laser"}, with_ink=True)
    tui.execute("board on")
    tui.execute("blackout")
    assert (tui.deck.board, tui.deck.blackout) == (True, True)
    tui.execute("color red")
    assert tui.ink is not None
    assert tui.ink.tool.color == "#e53935"
    tui.execute("color nope")
    assert "colour:" in tui.message
    tui.execute("width 9")
    assert tui.ink.tool.width == 9.0
    tui.ink.begin("board", 1.0, 1.0, 1.0)
    tui.ink.extend("board", 50.0, 50.0, 1.0)
    tui.execute("undo")
    assert tui.ink.strokes("board") == []
    tui.execute("redo")
    assert len(tui.ink.strokes("board")) == 1
    tui.execute("clear")
    assert tui.ink.strokes("board") == []


def test_search_lists_hits_and_note_hit_previews_without_moving_projector(tmp_path: Path) -> None:
    tui, proj, _ = make(tmp_path)
    keys(tui, "/")
    assert tui.buffer == "/"
    type_line(tui, "carbuncle")
    assert tui.mode == "list"
    assert tui.items[0].startswith("notes (slide 2)")
    tui.handle_key("Enter")
    assert (tui.deck.view, tui.deck.page, proj.gotos) == (1, 0, [])
    tui.execute("search nothingmatcheshere")
    assert "no matches" in tui.message


def test_overview_picks_a_slide(tmp_path: Path) -> None:
    tui, proj, _ = make(tmp_path)
    keys(tui, "o")
    assert tui.mode == "list"
    assert tui.items[0].endswith("Title 0")
    keys(tui, "j j Enter")
    assert (tui.deck.view, proj.gotos) == (2, [2])
    assert tui.mode == "normal"


def test_timer_and_status_line(tmp_path: Path) -> None:
    tui, _, clock = make(tmp_path)
    keys(tui, "t")
    clock.now += 125
    frame = tui.render(100, 20)
    assert "2:05" in frame[0]
    assert "1/6" in frame[0]
    tui.execute("target 5")
    assert tui.timer.target_min == 5


def test_render_fits_the_terminal_and_shows_notes_and_preview(tmp_path: Path) -> None:
    tui, _, _ = make(tmp_path, preview=True)
    keys(tui, "l")
    frame = tui.render(100, 24)
    assert len(frame) == 24
    assert all(visible_len(line) == 100 for line in frame)
    text = "\n".join(frame)
    assert "carbuncle" in text
    assert "PREVIEW" in text
    assert "│" in text
    narrow = tui.render(60, 10)
    assert "PREVIEW" not in "\n".join(narrow)
    assert len(narrow) == 10


def test_snapshot_restore_roundtrip(tmp_path: Path) -> None:
    tui, _, _ = make(tmp_path)
    keys(tui, "3 l t")
    snap = tui.snapshot()
    other, proj, _ = make(tmp_path)
    other.restore(snap)
    assert (other.deck.view, other.timer.running) == (THIRD, True)
    proj.gotos.clear()
    other.project_now()
    assert proj.gotos == [THIRD]


def test_null_projector_is_harmless() -> None:
    projector = NullProjector()
    projector.goto(1)
    projector.fullscreen(True)
    assert projector.is_fullscreen() is False
    assert projector.caps == frozenset()


def test_projector_errors_become_messages(tmp_path: Path) -> None:
    class Broken(FakeProjector):
        def goto(self, page: int) -> None:
            raise RuntimeError("window closed")

    tui, _, _ = make(tmp_path)
    broken = Tui(MarkdownNotes(tmp_path / "n.md"), Options(), Broken(), PdfInfo(PAGES, lambda: TEXTS), FakeClock())
    broken.handle_key("l")
    assert broken.message == "projector: window closed"
    assert tui.running


def test_unreadable_notes_do_not_crash(tmp_path: Path) -> None:
    tui = Tui(
        MarkdownNotes(tmp_path / "missing.md"), Options(), FakeProjector(), PdfInfo(PAGES, lambda: TEXTS), FakeClock()
    )
    assert tui.message
    assert tui.render(80, 10)


@pytest.mark.parametrize("key", ["Esc", "x", "Up", "Down", "Home", "End", "PageUp", "PageDown"])
def test_misc_keys_never_raise(tmp_path: Path, key: str) -> None:
    tui, _, _ = make(tmp_path)
    tui.handle_key(key)
    assert tui.render(80, 12)


def test_every_terminal_command_has_help(tmp_path: Path) -> None:
    tui, _, _ = make(tmp_path, GTK_CAPS, with_ink=True)
    assert set(tui._commands) <= set(commands.HELP)


def test_help_lists_commands_with_keys_and_what_is_unavailable(tmp_path: Path) -> None:
    tui, _, _ = make(tmp_path)  # zathura-like projector: no capabilities
    keys(tui, "?")
    assert tui.mode == "list"
    text = "\n".join(tui.items)
    assert "goto N" in text
    assert "[key l]" in text
    assert "Navigation" in tui.items[0]
    board = next(item for item in tui.items if " board [on|off]" in item)
    assert "not supported by this projector" in board
    laser = next(item for item in tui.items if "laser [on|off]" in item)
    assert "needs the GTK console" in laser
    assert any("quit" in item for item in tui.items)


def test_help_pick_starts_typing_the_command(tmp_path: Path) -> None:
    tui, _, _ = make(tmp_path)
    keys(tui, "?")
    index = next(i for i, item in enumerate(tui.items) if " goto N " in item)
    tui.cursor = index
    tui.handle_key("Enter")
    assert (tui.mode, tui.buffer) == ("command", ":goto ")
    type_line(tui, "4")
    assert tui.deck.view == THIRD


def test_help_for_one_command(tmp_path: Path) -> None:
    tui, _, _ = make(tmp_path)
    tui.execute("help freeze")
    assert tui.message.startswith("freeze [on|off]:")
    assert tui.mode == "normal"
    tui.execute("help nonsense")
    assert "no such command" in tui.message


def test_drawing_commands_with_a_gtk_projector(tmp_path: Path) -> None:
    tui, _, _ = make(tmp_path, GTK_CAPS - {"laser"}, with_ink=True)
    assert tui.ink is not None
    tui.execute("smooth 3")
    tui.execute("eraser-size 30")
    tui.execute("highlight-alpha 0.5")
    tui.execute("highlighter on")
    tui.execute("board-style grid")
    assert (tui.ink.tool.smoothing, tui.ink.tool.eraser_radius, tui.ink.tool.highlight_alpha) == (3, 30.0, 0.5)
    assert (tui.ink.tool.highlighter, tui.deck.board_style) == (True, "grid")
    tui.execute("smooth 9")
    assert "smooth needs" in tui.message
    tui.ink.begin("s0", 0.0, 0.0, 1.0)
    tui.ink.begin("board", 0.0, 0.0, 1.0)
    tui.execute("clear-all")
    assert "erased 2 strokes" in tui.message
    assert not tui.ink.strokes("s0")


@pytest.mark.parametrize("name", ["export", "laser-color red", "layout wide", "upcoming 4"])
def test_gtk_only_commands_are_explained(tmp_path: Path, name: str) -> None:
    tui, _, _ = make(tmp_path, GTK_CAPS - {"laser"}, with_ink=True)
    tui.execute(name)
    assert "needs the GTK console" in tui.message


def test_drawing_commands_without_a_gtk_projector_say_so(tmp_path: Path) -> None:
    tui, _, _ = make(tmp_path)
    for name in ("clear-all", "highlighter on", "color red", "board-style grid"):
        tui.execute(name)
        assert tui.message in ("no ink store", "not supported by this projector") or "not supported" in tui.message, (
            name
        )


def test_search_results_are_a_panel_that_leaves_the_slides_and_notes_visible(tmp_path: Path) -> None:
    tui, _, _ = make(tmp_path)
    keys(tui, "/")
    type_line(tui, "carbuncle")
    assert (tui.mode, tui.list_panel) == ("list", True)
    frame = "\n".join(tui.render(100, 30))
    assert "search: carbuncle" in frame  # the panel title
    assert "Two" in frame or "carbuncle" in frame  # the notes above it are still drawn
    assert "intro" in frame
    tui.handle_key("Enter")  # picks the hit but keeps the panel open
    assert (tui.mode, tui.list_panel) == ("list", True)
    tui.handle_key("Esc")
    assert (tui.mode, tui.list_panel) == ("normal", False)


def test_full_screen_lists_stay_full_screen(tmp_path: Path) -> None:
    tui, _, _ = make(tmp_path)
    keys(tui, "o")
    assert (tui.mode, tui.list_panel) == ("list", False)
    assert "intro" not in "\n".join(tui.render(100, 30))


def test_lecture_length_formats(tmp_path: Path) -> None:
    tui, _, _ = make(tmp_path)
    tui.execute("target 1h30")
    assert tui.timer.target_min == 90
    tui.execute("target 2:15")
    assert tui.timer.target_min == 135
    tui.execute("target x")
    assert "target needs a length" in tui.message
    assert tui.timer.target_min == 135
