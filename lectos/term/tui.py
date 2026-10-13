"""Terminal presenter console (no GTK): notes, previews, timer, search and a Zathura projector.

``Tui`` holds all behaviour as keys in, frame lines out, so it is testable without a terminal.
Limited by design: no ink, laser, chalkboard, blackout or rendered math images; those need ``lectos``.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from lectos import state
from lectos.config import Options
from lectos.control import commands, search
from lectos.control.keys import Vim, key_for
from lectos.control.toolcmds import TOOL_FLAG_MESSAGES, Tools
from lectos.i18n import noop, tr
from lectos.model.deck import Deck, Timer, format_seconds, parse_minutes, schedule_summary
from lectos.model.ink import Ink
from lectos.notes import markdown
from lectos.notes.beamer import open_notes
from lectos.notes.markdown import NotesError, NotesSource, Section
from lectos.projectors.projection import COMMAND_CAPS, NullProjector, Projector, ProjectorSync, apply_caps
from lectos.term import pdftools
from lectos.term.pdftools import PdfToolError
from lectos.term.tuiterm import Terminal
from lectos.term.tuitext import pad, wrap

if TYPE_CHECKING:  # the stage needs cairo; the terminal console only reads layer names from it
    from lectos.draw.stage import Stage

SCROLL_STEP = 2
PREVIEW_MIN_WIDTH = 90
PREVIEW_MAX_COLS = 60
PREVIEW_ROW_RATIO = 0.3  # terminal cells are about twice as tall as wide; slides are 16:9
LOOP_S = 0.25
SAVE_EVERY_S = 2.0
GTK_ONLY = {
    "laser", "laser-color", "laser-size", "laser-style", "show-slide", "vim", "projector-fullscreen", "export",
    "layout", "upcoming", "previous", "sketch", "panel", "settings", "edit", "open", "export-ink",
}  # fmt: skip
HINT = noop(" :command  /search  o overview  l/h next/prev  j/k scroll  ? help")  # shown through tr()
PANEL_ROWS = 9  # most rows the search-result panel takes at the bottom
MIN_MAIN_ROWS = 4  # below this the panel would hide the slides, so it falls back to full screen
REVERSE = "\x1b[7m"
RESET = "\x1b[0m"


@dataclass
class PdfInfo:
    """What the console knows about the slides; ``preview`` is None when chafa/pdftoppm are missing."""

    pages: int
    texts: Callable[[], tuple[str, ...]]
    preview: Callable[[int, int, int], list[str]] | None = None


class Tui:
    """Presenter console state machine."""

    def __init__(
        self,
        notes_source: NotesSource | None,
        options: Options,
        projector: Projector,
        pdf: PdfInfo,
        clock: Callable[[], float],
        *,
        deck: Deck | None = None,
        ink: Ink | None = None,
        stage: Stage | None = None,
    ) -> None:
        self.source, self.projector, self.pdf, self.clock = notes_source, projector, pdf, clock
        self.ink, self.stage = ink, stage
        self._help_names: list[str] = []
        self.deck = deck or Deck(pdf.pages)
        self.tools = Tools(ink, self.deck, stage.laser) if ink is not None and stage is not None else None
        self.timer = Timer(target_min=options.target_min)
        self.vim = Vim()
        self.mode = "normal"  # normal | command | list
        self.buffer = ""
        self.list_title, self.items, self.cursor = "", [], 0
        self.list_panel = False
        self.on_pick: Callable[[int], None] = lambda _i: None
        self.message = ""
        self.running = True
        self.dirty = False
        self.hits: list[search.Hit] = []
        self.hit = -1
        self.show_slide = True
        self.scroll = 0
        self._follow = True
        self._focus_section: int | None = None
        self._sections: list[Section] = []
        self._notes_stamp = -1
        self._layout: tuple[tuple[int, int], list[str], list[int], list[int]] | None = None
        self._notes_gen = 0
        self._fullscreen_on = False
        self._commands = self._build_commands()
        self.sync = ProjectorSync(self.deck, projector, self._set_message)
        self.deck.subscribe(self._on_deck)
        self.poll_notes()

    # ---- state ----
    def _on_deck(self) -> None:
        self.dirty = True
        self._follow = True

    def snapshot(self) -> dict[str, object]:
        """State to save: pages, freeze, timer and notes position."""
        return {**self.deck.to_dict(), "timer": self.timer.to_dict(), "notes_scroll": self.scroll}

    def restore(self, saved: dict[str, object]) -> None:
        """Apply saved state."""
        self.deck.load(saved)
        self.timer.load(saved.get("timer"))
        scroll = saved.get("notes_scroll")
        if isinstance(scroll, int | float) and not isinstance(scroll, bool):
            self.scroll, self._follow = max(0, int(scroll)), False
        self.dirty = False

    def refresh_pdf(self, pdf: PdfInfo) -> None:
        """Adopt a recompiled PDF."""
        self.pdf = pdf
        self.deck.set_pages(pdf.pages)

    def poll_notes(self) -> None:
        """Reload the notes when their source changed."""
        if self.source is None:
            return
        try:
            stamp = self.source.stamp()
            if stamp == self._notes_stamp:
                return
            self._sections = self.source.load()
        except (NotesError, OSError) as exc:
            self.message = str(exc)
            return
        self._notes_stamp = stamp
        self._notes_gen += 1

    # ---- commands ----
    def _build_commands(self) -> dict[str, Callable[[str], None]]:
        deck, c = self.deck, commands
        table = {
            "next": lambda a: deck.step(c.count(a)),
            "prev": lambda a: deck.step(-c.count(a)),
            "goto": self._cmd_goto,
            "first": lambda _a: deck.goto(0),
            "last": lambda _a: deck.goto(deck.pages - 1),
            "scroll-down": lambda a: self._scroll(c.count(a) * SCROLL_STEP),
            "scroll-up": lambda a: self._scroll(-c.count(a) * SCROLL_STEP),
            "search": self._cmd_search,
            "hit-next": lambda _a: self.show_hit(self.hit + 1),
            "hit-prev": lambda _a: self.show_hit(self.hit - 1),
            "overview": lambda _a: self._open_overview(),
            "main": lambda _a: self._close_overlay(),
            "freeze": lambda a: deck.set_frozen(c.flag(a, deck.frozen)),
            "timer": lambda _a: self.timer.toggle(self.clock()),
            "timer-reset": lambda _a: self.timer.reset(),
            "target": self._cmd_target,
            "fullscreen": lambda a: self._fullscreen(c.flag(a, self._fullscreen_on)),
            "help": self._cmd_help,
            "quit": lambda _a: self._quit(),
            "q": lambda _a: self._quit(),
            "blackout": lambda a: self._cmd_blackout(c.flag(a, deck.blackout)),
            "board": lambda a: self._cmd_board(c.flag(a, deck.board)),
            "draw": lambda a: self._set_tool_flag("mouse_draw", c.flag(a, self._tool_value("mouse_draw"))),
            "eraser": lambda a: self._set_tool_flag("eraser", c.flag(a, self._tool_value("eraser"))),
            "undo": lambda _a: self._with_ink(lambda ink, layer: ink.undo(layer)),
            "redo": lambda _a: self._with_ink(lambda ink, layer: ink.redo(layer)),
            "clear": lambda _a: self._with_ink(lambda ink, layer: ink.clear(layer)),
            "color": lambda a: self._tool("color", a),
            "width": lambda a: self._tool("width", a),
            "smooth": lambda a: self._tool("smoothing", a),
            "eraser-size": lambda a: self._tool("eraser_size", a),
            "highlight-alpha": lambda a: self._tool("highlight_alpha", a),
            "board-style": lambda a: self._tool("board_style", a),
            "highlighter": lambda a: self._tool("highlighter", c.flag(a, self._tool_value("highlighter"))),
            "clear-all": lambda _a: self._tool("clear_all"),
            "restore-all": lambda _a: self._tool("restore_all"),
        }
        return apply_caps(table, self.projector.caps, self._set_message)

    def _cmd_blackout(self, on: bool) -> None:
        if on != self.deck.blackout:
            self.deck.toggle_blackout()

    def _cmd_board(self, on: bool) -> None:
        if on != self.deck.board:
            self.deck.toggle_board()

    def _tool_value(self, name: str) -> bool:
        return self.ink is not None and bool(getattr(self.ink.tool, name))

    def _set_tool_flag(self, name: str, value: bool) -> None:
        if self.ink is None:
            self.message = tr("no ink store")
            return
        setattr(self.ink.tool, name, value)
        off, on = TOOL_FLAG_MESSAGES[name]
        self.message = tr("{message} (draw on the projector window)").format(message=tr(on if value else off))

    def _with_ink(self, action: Callable[[Ink, str], None]) -> None:
        if self.ink is None or self.stage is None:
            self.message = tr("no ink store")
        else:
            action(self.ink, self.stage.layer(self.deck.page))  # the projector window is where the pen draws

    def _tool(self, method: str, *args: object) -> None:
        """Run a pen/board setting from ``Tools`` and show its message."""
        self.message = tr("no ink store") if self.tools is None else getattr(self.tools, method)(*args)

    def execute(self, line: str) -> None:
        """Run one command line, the single path used by keys and the command line."""
        text = line.strip()
        name, arg = ("search", text[1:].strip()) if text.startswith("/") else commands.parse(text)
        handler = self._commands.get(name)
        if handler is None:
            self.message = (
                tr("{name}: needs the GTK console (lectos)").format(name=name)
                if name in GTK_ONLY
                else tr("unknown command: {name} (:help)").format(name=name)
            )
            return
        self.message = ""
        handler(arg)

    def _set_message(self, message: str) -> None:
        self.message = message

    def _quit(self) -> None:
        self.running = False

    def _cmd_help(self, arg: str) -> None:
        """``help``: a list of every command usable here (pick one to start typing it); ``help NAME``: one line."""
        if arg:
            self.message = commands.describe(arg, key_for)
            return
        unsupported = {name for name, cap in COMMAND_CAPS.items() if cap not in self.projector.caps}
        entries = commands.help_entries([*self._commands, *GTK_ONLY], key_for)
        self._help_names = [usage.split()[0] for _, usage, _, _ in entries]
        items = [
            f"{tr(group):<10} {usage:<32} {tr(text)}"
            + (f"  [{tr('key')} {key}]" if key else "")
            + (tr("  (needs the GTK console)") if usage.split()[0] in GTK_ONLY else "")
            + (tr("  (not supported by this projector)") if usage.split()[0] in unsupported else "")
            for group, usage, text, key in entries
        ]
        self._open_list(tr("help - Enter starts typing the command"), items, 0, self._help_pick)

    def _help_pick(self, index: int) -> None:
        self._open_prompt(f":{self._help_names[index]} ")

    def _cmd_goto(self, arg: str) -> None:
        if arg.isdigit():
            self.deck.goto(int(arg) - 1)
        else:
            self.message = tr("goto needs a slide number")

    def _cmd_target(self, arg: str) -> None:
        minutes = parse_minutes(arg)
        if minutes is None:
            self.message = tr("target needs a length like 90, 1h30, 1:30 or 45m (at most 24 h)")
            return
        self.timer.target_min = minutes
        self.dirty = True

    def _fullscreen(self, on: bool) -> None:
        try:
            self.projector.fullscreen(on)
            self._fullscreen_on = on
        except RuntimeError as exc:  # ProjectorError and friends
            self.message = tr("projector: {error}").format(error=exc)

    def _scroll(self, lines: int) -> None:
        self.scroll = max(0, self.scroll + lines)
        self._follow = False
        self.dirty = True

    # ---- search and overview ----
    def _cmd_search(self, arg: str) -> None:
        if not arg:
            self._open_prompt("/")
            return
        try:
            texts = self.pdf.texts()
        except PdfToolError as exc:
            self.message = str(exc)
            return
        self.hits = search.find(arg, texts, [(s.slide, s.text) for s in self._sections])
        self.hit = -1
        if not self.hits:
            self.message = tr("no matches for {query}").format(query=repr(arg))
            return
        items = [f"{self._hit_kind(h)}: {h.snippet}" for h in self.hits]
        self._open_list(tr("search: {query}").format(query=arg), items, 0, self.show_hit, panel=True)

    def show_hit(self, index: int) -> None:
        """Jump to a hit: slide hits move the view and projector, note hits scroll the notes."""
        if not self.hits:
            return
        self.hit = index % len(self.hits)
        h = self.hits[self.hit]
        if h.kind == "slide":
            self.deck.goto(h.index)
            return
        if h.slide and self.show_slide:
            self.deck.peek(h.slide - 1)  # preview only: the projector is not moved
        self._follow = False
        self._focus_section = h.index

    def _open_overview(self) -> None:
        try:
            texts = self.pdf.texts()
        except PdfToolError as exc:
            self.message = str(exc)
            return
        items = [
            f"{i + 1:>4}  {next((ln.strip() for ln in t.splitlines() if ln.strip()), tr('(blank)'))}"
            for i, t in enumerate(texts)
        ]
        self._open_list(tr("overview"), items, self.deck.view, self._goto_index)

    def _goto_index(self, index: int) -> None:
        self.deck.goto(index)

    def _open_list(
        self, title: str, items: list[str], cursor: int, on_pick: Callable[[int], None], *, panel: bool = False
    ) -> None:
        """Show a pick list: full screen, or (``panel``) at the bottom so the slides and notes stay visible."""
        self.mode, self.list_title, self.items, self.cursor, self.on_pick = "list", title, items, cursor, on_pick
        self.list_panel = panel

    @staticmethod
    def _hit_kind(hit: search.Hit) -> str:
        if hit.kind == "slide":
            return tr("slide {n}").format(n=hit.slide)
        return tr("notes (slide {n})").format(n=hit.slide) if hit.slide else tr("notes")

    def _close_overlay(self) -> None:
        self.mode, self.buffer, self.list_panel = "normal", "", False

    def _open_prompt(self, prefix: str) -> None:
        self.mode, self.buffer = "command", prefix

    # ---- keys ----
    def handle_key(self, key: str) -> None:
        """Process one key."""
        {"normal": self._key_normal, "command": self._key_command, "list": self._key_list}[self.mode](key)

    def _key_normal(self, key: str) -> None:
        simple = {
            "Right": "next", " ": "next", "PageDown": "next", "Left": "prev", "PageUp": "prev",
            "Home": "first", "End": "last", "Down": "scroll-down", "Up": "scroll-up",
        }  # fmt: skip
        if key == "C-c":
            self._quit()
        elif key == "Esc":
            self.vim.reset()
            self.message = ""
        elif key in simple:
            self.execute(simple[key])
        elif len(key) == 1:
            self._vim(key)

    def _vim(self, char: str) -> None:
        action = self.vim.feed(char)
        if action is None or action.name == "pending":
            return
        if action.name in ("command-line", "search") and action.count is None:
            self._open_prompt(":" if action.name == "command-line" else "/")
        else:
            self.execute(f"{action.name} {'' if action.count is None else action.count}")

    def _key_command(self, key: str) -> None:
        if key in ("Esc", "C-c"):
            self._close_overlay()
        elif key == "Enter":
            line = self.buffer
            self._close_overlay()
            self.execute(line)
        elif key == "Backspace":
            self.buffer = self.buffer[:-1]
            if not self.buffer:
                self._close_overlay()
        elif key == "Tab" and self.buffer.startswith(":"):
            self.buffer, matches = commands.complete(self.buffer, self._commands)
            self.message = "  ".join(matches) if len(matches) > 1 else ""
        elif len(key) == 1:
            self.buffer += key

    def _key_list(self, key: str) -> None:
        moves = {"j": 1, "Down": 1, "k": -1, "Up": -1, "PageDown": 10, "PageUp": -10}
        if key in ("Esc", "q", "C-c"):
            self._close_overlay()
        elif key in moves:
            self.cursor = max(0, min(self.cursor + moves[key], len(self.items) - 1))
        elif key in ("g", "Home"):
            self.cursor = 0
        elif key in ("G", "End"):
            self.cursor = len(self.items) - 1
        elif key == "Enter":
            index, pick = self.cursor, self.on_pick
            if not self.list_panel:
                self._close_overlay()  # the search panel stays open so you can step through the other hits
            pick(index)

    # ---- rendering ----
    def tick(self) -> None:
        """Periodic work: reload changed notes."""
        self.poll_notes()

    def render(self, width: int, height: int) -> list[str]:
        """The whole screen as ANSI lines of at most ``width`` cells; ``height`` lines."""
        body_h = max(1, height - 2)
        body = self._body(width, body_h)
        lines = [self._status(width), *body[:body_h], *[""] * (body_h - len(body)), self._footer(width)]
        return [pad(line, width) for line in lines]

    def _body(self, width: int, height: int) -> list[str]:
        if self.mode != "list":
            return self._main_body(width, height)
        rows = min(len(self.items) + 1, PANEL_ROWS)
        if self.list_panel and height - rows >= MIN_MAIN_ROWS:
            return [*self._main_body(width, height - rows)[: height - rows], *self._list_body(width, rows)]
        return self._list_body(width, height)

    def _status(self, width: int) -> str:
        now = self.clock()
        deck, timer = self.deck, self.timer
        parts = [
            f" {deck.view + 1}/{deck.pages}",
            tr("(proj {n})").format(n=deck.page + 1) if deck.page != deck.view else "",
            tr("[frozen]") if deck.frozen else "",
            f"{format_seconds(timer.elapsed(now))} / {format_seconds(timer.left(now))}"
            + ("" if timer.running else " " + tr("(paused)")),
            schedule_summary(timer, now, deck.view, deck.pages),
        ]
        return f"{REVERSE}{pad('  '.join(p for p in parts if p), width)}{RESET}"

    def _footer(self, width: int) -> str:
        if self.mode == "command":
            return f"{self.buffer}{REVERSE} {RESET}"
        if self.mode == "list":
            return tr(" j/k move  Enter pick  Esc back")
        return self.message or tr(HINT)

    def _list_body(self, width: int, height: int) -> list[str]:
        window = max(1, height - 1)
        top = max(0, min(self.cursor - window // 2, len(self.items) - window))
        rows = [f"\x1b[1m {self.list_title}\x1b[0m"]
        for i in range(top, min(len(self.items), top + window)):
            row = pad(f" {self.items[i]}", width)
            rows.append(f"{REVERSE}{row}{RESET}" if i == self.cursor else row)
        return rows

    def _notes_layout(self, width: int) -> tuple[list[str], list[int], list[int]]:
        """Wrapped note lines, the first line of each section, and the section owning each line."""
        key = (width, self._notes_gen)
        if self._layout is None or self._layout[0] != key:
            lines: list[str] = []
            starts: list[int] = []
            owners: list[int] = []
            for i, section in enumerate(self._sections):
                starts.append(len(lines))
                block = [*wrap(markdown.parse(section.text), width - 2), ""]
                lines += block
                owners += [i] * len(block)
            self._layout = (key, lines, starts, owners)
        return self._layout[1], self._layout[2], self._layout[3]

    def _main_body(self, width: int, height: int) -> list[str]:
        side = self.pdf.preview is not None and width >= PREVIEW_MIN_WIDTH
        cols = min(PREVIEW_MAX_COLS, (width - 3) // 2) if side else 0
        notes_w = width - cols - 3 if side else width
        right = self._notes_body(notes_w, height)
        if not side:
            return right
        left = self._preview_column(cols, height)
        return [f"{pad(a, cols)} │ {b}" for a, b in zip(left, right, strict=True)]

    def _notes_body(self, width: int, height: int) -> list[str]:
        lines, starts, owners = self._notes_layout(width)
        if self._focus_section is not None and self._focus_section < len(starts):
            self.scroll, self._focus_section = starts[self._focus_section], None
        elif self._follow:
            current = next((i for i, s in enumerate(self._sections) if s.slide == self.deck.view + 1), None)
            if current is not None:
                self.scroll = starts[current]
            self._follow = False
        self.scroll = max(0, min(self.scroll, max(0, len(lines) - height)))
        shown = lines[self.scroll : self.scroll + height]
        marks = [
            "▌ " if self._sections[owners[i]].slide == self.deck.view + 1 else "  "
            for i in range(self.scroll, self.scroll + len(shown))
        ]
        out = [f"{m}{ln}" for m, ln in zip(marks, shown, strict=True)]
        return out + [""] * (height - len(out))

    def _preview_column(self, cols: int, height: int) -> list[str]:
        rows = max(4, int(cols * PREVIEW_ROW_RATIO))
        assert self.pdf.preview is not None
        column: list[str] = []
        for label, page in ((noop("view"), self.deck.view), (noop("next"), self.deck.view + 1)):
            if page >= self.deck.pages or len(column) + rows + 1 > height:
                continue
            column.append(f"\x1b[2m{tr(label)} {page + 1}\x1b[0m")
            try:
                column += self.pdf.preview(page, cols, rows)
            except PdfToolError as exc:
                column.append(str(exc))
        return column + [""] * (height - len(column))


# ---- runtime ----
def pdf_info(pdf: Path) -> PdfInfo:
    """Page count, text and (when chafa and pdftoppm exist) previews of a PDF."""

    def preview(page: int, cols: int, rows: int) -> list[str]:
        return pdftools.preview(pdf, page, cols, rows)

    def texts() -> tuple[str, ...]:
        return pdftools.page_texts(pdf)

    return PdfInfo(pdftools.page_count(pdf), texts, preview if pdftools.previews_available() else None)


class Runner:
    """One loop iteration of work, called by whichever event loop drives the console."""

    def __init__(self, tui: Tui, terminal: Terminal, pdf: Path, extra_save: Callable[[], None] | None = None) -> None:
        self.tui, self.terminal, self.pdf, self.extra_save = tui, terminal, pdf, extra_save
        self._last: list[str] = []
        self._mtime = pdf.stat().st_mtime_ns
        self._next_save = time.monotonic() + SAVE_EVERY_S

    def step(self, keys: list[str]) -> None:
        """Handle keys, reload what changed, redraw if the frame changed, autosave."""
        for key in keys:
            self.tui.handle_key(key)
        self.tui.tick()
        self._reload_pdf()
        frame = self.tui.render(*self.terminal.size())
        if frame != self._last:
            self.terminal.draw(frame)
            self._last = frame
        if self.tui.dirty and time.monotonic() >= self._next_save:
            self.tui.dirty = False
            self.save()
            self._next_save = time.monotonic() + SAVE_EVERY_S

    def _reload_pdf(self) -> None:
        mtime = self.pdf.stat().st_mtime_ns
        if mtime != self._mtime:
            self._mtime = mtime
            self.tui.refresh_pdf(pdf_info(self.pdf))

    def save(self) -> None:
        """Write recovery state (and ink, when there is any)."""
        try:
            state.save(self.pdf, {**state.load(self.pdf), **self.tui.snapshot()})
        except (OSError, ValueError) as exc:
            print(f"lectos: cannot save state: {exc}", file=sys.stderr)
        if self.extra_save is not None:
            self.extra_save()


def run_select(tui: Tui, pdf: Path) -> None:
    """Drive the console with a plain select loop (no GTK main loop needed)."""
    try:
        with Terminal() as terminal:
            runner = Runner(tui, terminal, pdf)
            try:
                while tui.running:
                    runner.step(terminal.read_keys(LOOP_S))
            finally:
                runner.save()
    except KeyboardInterrupt:
        pass


def make_tui(
    pdf: Path,
    notes: Path | None,
    options: Options,
    projector: Projector,
    *,
    deck: Deck | None = None,
    ink: Ink | None = None,
    stage: Stage | None = None,
) -> Tui:
    """Build the console for a PDF, restore saved state and put the projector on the saved page."""
    source = open_notes(notes, pdf) if notes else None
    tui = Tui(source, options, projector, pdf_info(pdf), time.time, deck=deck, ink=ink, stage=stage)
    tui.restore(state.load(pdf))  # restoring moves the deck, which puts the projector on the saved page
    return tui


__all__ = ["NullProjector", "PdfInfo", "Runner", "Tui", "make_tui", "pdf_info", "run_select"]
