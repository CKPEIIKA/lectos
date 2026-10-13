"""Fixtures for the GTK tests: real windows on a real display. Without GTK or a display none of them run."""

import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

try:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Adw, Gdk, Gio, GLib

    HAVE_DISPLAY = Gdk.Display.get_default() is not None
except (ImportError, ValueError):
    HAVE_DISPLAY = False

collect_ignore_glob = [] if HAVE_DISPLAY else ["test_*.py", "widgets/test_*.py"]
EXAMPLES = Path(__file__).resolve().parents[2] / "examples"

if HAVE_DISPLAY:
    from lectos import config
    from lectos.gtk.app import Core, build_core
    from lectos.gtk.console import ConsoleWindow
    from lectos.notes import mathimg
    from lectos.notes.beamer import open_notes
    from lectos.projectors.projection import GTK_CAPS, NullProjector

    class GtkProjector(NullProjector):
        """A projector with every capability that records what it was asked to do."""

        caps = GTK_CAPS

        def __init__(self) -> None:
            self.pages: list[int] = []
            self.full = False

        def goto(self, page: int) -> None:
            self.pages.append(page)

        def fullscreen(self, on: bool) -> None:
            self.full = on

        def is_fullscreen(self) -> bool:
            return self.full

    class Rig:
        """A console with its core and projector."""

        def __init__(self, console: ConsoleWindow, core: Core, projector: NullProjector) -> None:
            self.console, self.core, self.projector = console, core, projector

    def _pump(seconds: float = 0.0) -> None:
        """Run the GLib main loop for ``seconds`` (and until nothing is pending)."""
        context = GLib.MainContext.default()
        end = time.monotonic() + seconds
        while context.pending() or time.monotonic() < end:
            context.iteration(False)
            if not context.pending():
                time.sleep(0.005)

    @pytest.fixture
    def pump() -> Callable[[float], None]:
        return _pump

    @pytest.fixture
    def wait_for() -> Callable[..., bool]:
        def wait(condition: Callable[[], bool], seconds: float = 5.0) -> bool:
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                _pump(0.02)
                if condition():
                    return True
            return False

        return wait

    @pytest.fixture(scope="session")
    def application() -> Adw.Application:
        app = Adw.Application(application_id="org.lectos.tests", flags=Gio.ApplicationFlags.NON_UNIQUE)
        app.register()
        return app

    @pytest.fixture
    def build_rig(application: Adw.Application, monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., Rig]]:
        """Factory ``build_rig(caps=, notes=True | Path | False, options=)``; windows are destroyed afterwards."""
        monkeypatch.setattr(mathimg, "render", lambda formulas, **_k: {})  # no LaTeX in these tests
        made: list[Rig] = []

        def build(*, caps: bool = True, notes: "bool | Path" = True, options: "config.Options | None" = None) -> Rig:
            options = options or config.Options()
            projector: NullProjector = GtkProjector() if caps else NullProjector()
            core = build_core(EXAMPLES / "slides.pdf", projector.caps, options)
            notes_file = EXAMPLES / "slides.tex" if notes is True else notes  # True: the sample deck's Beamer notes
            source = open_notes(notes_file, EXAMPLES / "slides.pdf") if notes_file else None
            console = ConsoleWindow(
                application, core.stage, doc=core.doc, projector=projector, notes=source, options=options
            )
            made.append(Rig(console, core, projector))
            _pump(0.05)
            return made[-1]

        yield build
        for rig in made:
            rig.console.destroy()
        _pump(0.0)

    @pytest.fixture
    def rig(build_rig: Callable[..., Rig]) -> Rig:
        """A console with every projector capability and the sample deck's Beamer notes."""
        return build_rig(caps=True, notes=True)

    @pytest.fixture
    def plain(build_rig: Callable[..., Rig]) -> Rig:
        """A console whose projector (like Zathura) has no extra capabilities, and no notes."""
        return build_rig(caps=False, notes=False)
