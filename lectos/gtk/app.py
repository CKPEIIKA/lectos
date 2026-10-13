"""GTK console application: shared core, projector choice, polling and recovery state."""

from __future__ import annotations

import signal
import sys
from dataclasses import dataclass, field
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
from lectos.gtk.pdfdoc import AnnotationNotes, PdfDoc
from lectos.gtk.projector import ProjectorWindow, WindowProjector
from lectos.gtk.widgets.start import StartWindow
from lectos.i18n import tr
from lectos.model.deck import Deck
from lectos.model.ink import Ink
from lectos.model.style import LaserStyle
from lectos.notes.beamer import open_notes
from lectos.notes.markdown import NotesSource
from lectos.projectors.projection import GTK_CAPS, NullProjector, Projector, ProjectorSync
from lectos.projectors.zathura import Zathura

CONSOLE_ICON = "lectos"
ICON_DIR = Path(__file__).parent / "icons"
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
    doc = PdfDoc(pdf, options.notes_pages)
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


def register_icons() -> None:
    """Make the bundled application icons known to the icon theme (once per process)."""
    theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
    if str(ICON_DIR) not in (theme.get_search_path() or []):
        theme.add_search_path(str(ICON_DIR))


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
    window = ProjectorWindow(app, core.stage, core.ink, chosen, options.blackout, name=pdf.name)
    window.present()
    projector = WindowProjector(window)
    if not windowed and count > 1:
        projector.fullscreen(True)  # one monitor: stay windowed so the console remains usable
    return projector


@dataclass
class Session:
    """One presented deck: its windows, projector and the GLib sources that serve it."""

    pdf: Path
    console: ConsoleWindow
    core: Core
    projector: Projector
    sources: list[int] = field(default_factory=list)

    def release(self) -> None:
        """Stop the timers, save the state and stop the projector."""
        for source in self.sources:
            GLib.source_remove(source)
        _save(self.pdf, self.console)
        save_ink(self.pdf, self.core.ink)
        self.projector.stop()

    def finish(self) -> None:
        """Release everything and drop the console, leaving the application running."""
        self.release()
        self.console.destroy()


def _start_timers(pdf: Path, core: Core, console: ConsoleWindow) -> list[int]:
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

    return [GLib.timeout_add(POLL_MS, poll), GLib.timeout_add(SAVE_MS, autosave)]


def _open_console(
    app: Gtk.Application, pdf: Path, core: Core, proj: Projector, *, notes: NotesSource | None, options: Options
) -> Session:
    console = ConsoleWindow(app, core.stage, doc=core.doc, projector=proj, notes=notes, options=options)
    sync = ProjectorSync(core.deck, proj, console.say)
    console.restore(core.saved)
    console.present()
    sync.force()
    session = Session(pdf, console, core, proj, _start_timers(pdf, core, console))
    console.connect("close-request", lambda *_: _on_close(session, app))
    session.sources.append(
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: console.close() or GLib.SOURCE_REMOVE)
    )  # Ctrl-C saves state
    return session


class Launcher:
    """Starts presenting a deck, from the command line or from the start window, and can switch decks."""

    def __init__(self, app: Gtk.Application, options: Options, *, projector: str, windowed: bool, monitor: int | None):
        self.app, self.options = app, options
        self.kind, self.windowed, self.monitor = projector, windowed, monitor
        self.failure: list[str] = []
        self.session: Session | None = None

    def begin(self, pdf: Path, notes: NotesSource | None) -> None:
        """Open the console (and our projector window if chosen) for a deck."""
        core = build_core(pdf, GTK_CAPS if self.kind == "gtk" else frozenset(), self.options)
        try:
            proj = make_projector(
                self.app, core, self.kind, self.options, pdf, windowed=self.windowed, monitor=self.monitor
            )
        except RuntimeError as exc:
            self.failure.append(str(exc))
            self.app.quit()
            return
        notes = notes or (AnnotationNotes(core.doc) if core.doc.annotations() else None)  # notes inside the PDF
        self.session = _open_console(self.app, pdf, core, proj, notes=notes, options=self.options)
        console = self.session.console
        console.opener = self.show_start
        if core.doc.notes_side and self.kind == "zathura":
            console.say(tr("the PDF has notes pages: Zathura would show them to the audience, use the gtk projector"))

    def show_start(self) -> None:
        """The window that chooses slides and notes."""
        start = StartWindow(self.app, lambda pdf, notes: self._chosen(start, pdf, notes))
        start.present()

    def _chosen(self, start: StartWindow, pdf: Path, notes: Path | None) -> None:
        if self.session is not None:
            self.session.finish()
            self.session = None
        self.begin(pdf, open_notes(notes, pdf) if notes else None)
        start.close()


def run(
    pdf: Path | None,
    notes: NotesSource | None,
    options: Options,
    *,
    projector: str,
    windowed: bool,
    monitor: int | None,
) -> int:
    """Open the console (and our projector window if chosen) and run until the console is closed.

    Without slides a start window asks for them.
    """
    app = Adw.Application(
        application_id="org.lectos.app", flags=Gio.ApplicationFlags.NON_UNIQUE
    )  # several decks can run at once
    launcher = Launcher(app, options, projector=projector, windowed=windowed, monitor=monitor)
    register_icons()
    Gtk.Window.set_default_icon_name(CONSOLE_ICON)
    app.connect("activate", lambda _a: launcher.show_start() if pdf is None else launcher.begin(pdf, notes))
    status = app.run([sys.argv[0]])
    if launcher.failure:
        print(f"lectos: {launcher.failure[0]}", file=sys.stderr)
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


def _on_close(session: Session, app: Gtk.Application) -> bool:
    session.release()
    app.quit()
    return False
