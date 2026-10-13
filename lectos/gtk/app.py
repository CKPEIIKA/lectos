"""GTK console application: shared core, projector choice, polling and recovery state."""

from __future__ import annotations

import signal
import sys
from dataclasses import dataclass
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GLibUnix", "2.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, GLibUnix, Gtk

from lectos import state
from lectos.config import Options
from lectos.draw.stage import Stage
from lectos.gtk.console import ConsoleWindow
from lectos.gtk.pdfdoc import PdfDoc
from lectos.gtk.projector import ProjectorWindow, WindowProjector
from lectos.model.deck import Deck
from lectos.model.ink import Ink
from lectos.model.style import LaserStyle
from lectos.notes.markdown import NotesSource
from lectos.projectors.projection import GTK_CAPS, NullProjector, Projector, ProjectorSync
from lectos.projectors.zathura import Zathura

POLL_MS = 1000
SAVE_MS = 2000


@dataclass
class Core:
    """Objects every GTK-based front end shares: the PDF, deck, ink and what the audience sees."""

    doc: PdfDoc
    deck: Deck
    ink: Ink
    stage: Stage
    saved: dict[str, object]


def build_core(pdf: Path, caps: frozenset[str], options: Options) -> Core:
    """Open the PDF and restore saved deck and ink.

    Options set the pen and laser defaults; features the projector lacks are switched off.
    """
    doc = PdfDoc(pdf)
    deck = Deck(doc.pages)
    deck.board_style = options.drawing.board
    saved = state.load(pdf)
    deck.load(saved)  # a saved board style wins over the configured default
    if "board" not in caps:
        deck.board = False
    ink = Ink()
    ink.load(state.load(pdf, "ink"))
    pen, tool = options.drawing, ink.tool
    tool.color, tool.width, tool.highlight_alpha = pen.color, pen.width, pen.highlighter_alpha
    tool.eraser_radius, tool.smoothing = pen.eraser_radius, pen.smoothing
    look = options.laser
    laser = LaserStyle(color=look.color, size=look.size, style=look.style, halo=look.halo)
    return Core(doc, deck, ink, Stage(doc, deck, ink, laser), saved)


def pick_monitor(index: int | None) -> tuple[Gdk.Monitor | None, int]:
    """The chosen monitor (default: last) and the number of monitors."""
    monitors = Gdk.Display.get_default().get_monitors()
    count = monitors.get_n_items()
    chosen = count - 1 if index is None else index
    return (monitors.get_item(chosen) if 0 <= chosen < count else None), count


def make_projector(
    app: Gtk.Application, core: Core, kind: str, options: Options, pdf: Path, *, windowed: bool, monitor: int | None
) -> Projector:
    """Our own GTK window, or Zathura driven over D-Bus. Raises ProjectorError if Zathura cannot start."""
    if kind == "none":
        return NullProjector()
    if kind == "zathura":
        zathura = Zathura(pdf.resolve())
        zathura.start()
        return zathura
    chosen, count = pick_monitor(monitor)
    window = ProjectorWindow(app, core.stage, core.ink, chosen, options.blackout)
    window.present()
    projector = WindowProjector(window)
    if not windowed and count > 1:
        projector.fullscreen(True)  # one monitor: stay windowed so the console remains usable
    return projector


def _start_timers(pdf: Path, core: Core, console: ConsoleWindow) -> None:
    def poll() -> bool:
        if core.doc.refresh():
            core.deck.set_pages(core.doc.pages)
        console.poll_notes()
        return True

    def autosave() -> bool:
        if console.dirty:
            console.dirty = False
            _save(pdf, console)
        save_ink(pdf, core.ink)
        return True

    GLib.timeout_add(POLL_MS, poll)
    GLib.timeout_add(SAVE_MS, autosave)


def _open_console(
    app: Gtk.Application, pdf: Path, core: Core, proj: Projector, *, notes: NotesSource | None, options: Options
) -> None:
    console = ConsoleWindow(app, core.stage, doc=core.doc, projector=proj, notes=notes, options=options)
    sync = ProjectorSync(core.deck, proj, console.say)
    console.restore(core.saved)
    console.present()
    sync.force()
    _start_timers(pdf, core, console)
    console.connect("close-request", lambda *_: _on_close(pdf, console, core.ink, proj, app))
    GLibUnix.signal_add(
        GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: console.close() or GLib.SOURCE_REMOVE
    )  # Ctrl-C saves state


def run(
    pdf: Path, notes: NotesSource | None, options: Options, *, projector: str, windowed: bool, monitor: int | None
) -> int:
    """Open the console (and our projector window if chosen) and run until the console is closed."""
    app = Adw.Application(
        application_id="org.lectos.app", flags=Gio.ApplicationFlags.NON_UNIQUE
    )  # several decks can run at once
    failure: list[str] = []

    def activate(app: Gtk.Application) -> None:
        core = build_core(pdf, GTK_CAPS if projector == "gtk" else frozenset(), options)
        try:
            proj = make_projector(app, core, projector, options, pdf, windowed=windowed, monitor=monitor)
        except RuntimeError as exc:
            failure.append(str(exc))
            app.quit()
            return
        _open_console(app, pdf, core, proj, notes=notes, options=options)

    app.connect("activate", activate)
    status = app.run([sys.argv[0]])
    if failure:
        print(f"lectos: {failure[0]}", file=sys.stderr)
        return 1
    return status


def _save(pdf: Path, console: ConsoleWindow) -> None:
    try:
        state.save(pdf, console.snapshot())
    except (OSError, ValueError) as exc:
        print(f"lectos: cannot save state: {exc}", file=sys.stderr)


def save_ink(pdf: Path, ink: Ink) -> None:
    """Write ink to its own state file when it changed."""
    if not ink.dirty:
        return
    try:
        state.save(pdf, ink.to_dict(), "ink")
    except (OSError, ValueError) as exc:
        print(f"lectos: cannot save ink: {exc}", file=sys.stderr)
        return
    ink.dirty = False


def _on_close(pdf: Path, console: ConsoleWindow, ink: Ink, projector: Projector, app: Gtk.Application) -> bool:
    _save(pdf, console)
    save_ink(pdf, ink)
    projector.stop()
    app.quit()
    return False
