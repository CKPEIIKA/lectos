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


def write_pdf(path: Path, pages: list[dict], names: dict[str, int] | None = None) -> Path:
    """Write a small PDF by hand. A page is ``{"size": (w, h), "text": ..., "text_right": ..., "links": [(rect,
    action)], "notes": [(rect, text)]}``; rects are PDF points (origin bottom-left); an action is a page index, an
    address, ``("named", name)`` or ``"next"``; ``names`` maps destination names to page indexes."""
    objs: dict[int, str] = {}
    number = 3
    font = number
    number += 1
    ids = []
    for _ in pages:
        ids.append((number, number + 1))
        number += 2
    annots: list[list[int]] = []
    for page in pages:
        count = len(page.get("links", [])) + len(page.get("notes", []))
        annots.append(list(range(number, number + count)))
        number += count
    dests = " ".join(f"({name}) [{ids[index][0]} 0 R /Fit]" for name, index in (names or {}).items())
    objs[1] = f"<< /Type /Catalog /Pages 2 0 R /Names << /Dests << /Names [{dests}] >> >> >>"
    objs[2] = f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p, _ in ids)}] /Count {len(pages)} >>"
    objs[font] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    for i, page in enumerate(pages):
        width, height = page.get("size", (400, 300))
        pid, cid = ids[i]
        stream = f"BT /F1 24 Tf 20 {height - 40} Td ({page.get('text', f'Page {i + 1}')}) Tj ET"
        if "text_right" in page:
            stream += f" BT /F1 24 Tf {width / 2 + 20} {height - 40} Td ({page['text_right']}) Tj ET"
        objs[cid] = f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream"
        made = iter(annots[i])
        for rect, action in page.get("links", []):
            if isinstance(action, int):
                target = f"/Dest [{ids[action][0]} 0 R /Fit]"
            elif isinstance(action, tuple):
                target = f"/Dest ({action[1]})"
            elif action == "next":
                target = "/A << /S /Named /N /NextPage >>"
            else:
                target = f"/A << /S /URI /URI ({action}) >>"
            objs[next(made)] = (
                f"<< /Type /Annot /Subtype /Link /Rect [{' '.join(map(str, rect))}] /Border [0 0 0] {target} >>"
            )
        for rect, text in page.get("notes", []):
            objs[next(made)] = (
                f"<< /Type /Annot /Subtype /Text /Rect [{' '.join(map(str, rect))}] /Contents ({text}) >>"
            )
        refs = " ".join(f"{a} 0 R" for a in annots[i])
        objs[pid] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /Contents {cid} 0 R "
            f"/Resources << /Font << /F1 {font} 0 R >> >> /Annots [{refs}] >>"
        )
    out = b"%PDF-1.4\n"
    offsets = {}
    for num in sorted(objs):
        offsets[num] = len(out)
        out += f"{num} 0 obj\n{objs[num]}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {number}\n0000000000 65535 f \n".encode()
    for num in range(1, number):
        out += f"{offsets[num]:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {number} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(out)
    return path


@pytest.fixture
def pdf_maker(tmp_path: Path):
    """``pdf_maker(pages, names=None, name="x.pdf")`` writes a hand-made PDF into the test's folder."""

    def make(pages: list[dict], names: dict[str, int] | None = None, name: str = "x.pdf") -> Path:
        return write_pdf(tmp_path / name, pages, names)

    return make


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

        def build(
            *,
            caps: bool = True,
            notes: "bool | Path" = True,
            options: "config.Options | None" = None,
            pdf: "Path | None" = None,
        ) -> Rig:
            options = options or config.Options()
            projector: NullProjector = GtkProjector() if caps else NullProjector()
            deck_pdf = pdf or EXAMPLES / "slides.pdf"
            core = build_core(deck_pdf, projector.caps, options)
            notes_file = EXAMPLES / "slides.tex" if notes is True else notes  # True: the sample deck's Beamer notes
            source = open_notes(notes_file, deck_pdf) if notes_file else None
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
