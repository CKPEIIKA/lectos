import os
import shutil
from pathlib import Path

import cairo
import pytest
from conftest import EXAMPLES
from gi.repository import Gdk, GLib, Gtk

from lectos import config
from lectos.gtk import app as app_module
from lectos.gtk.app import build_core, make_projector, pick_monitor, save_ink
from lectos.gtk.inkinput import InkInput
from lectos.gtk.pdfdoc import PdfDoc
from lectos.gtk.projector import ProjectorWindow, WindowProjector
from lectos.projectors.projection import GTK_CAPS, NullProjector
from lectos.projectors.zathura import ProjectorError

PDF = EXAMPLES / "slides.pdf"
NONE = Gdk.ModifierType(0)


# ---- pdfdoc ----
def test_a_document_reopens_when_its_file_changes(tmp_path) -> None:
    path = tmp_path / "d.pdf"
    shutil.copy(PDF, path)
    doc = PdfDoc(path)
    pages = doc.pages
    assert doc.refresh() is False
    doc.texts()
    doc.thumbnail(0, 40, 30)
    shutil.copy(PDF, path)
    os.utime(path, ns=(1, 1))
    assert doc.refresh() is True
    assert (doc.version, doc.pages) == (1, pages)
    assert doc._thumbs == {}


def test_a_file_that_is_mid_write_keeps_the_old_document(tmp_path) -> None:
    path = tmp_path / "d.pdf"
    shutil.copy(PDF, path)
    doc = PdfDoc(path)
    path.write_bytes(b"%PDF-1.5 truncated")
    os.utime(path, ns=(2, 2))
    assert doc.refresh() is False
    path.unlink()
    assert doc.refresh() is False
    assert doc.pages > 0


def test_thumbnails_are_cached_and_the_cache_is_bounded(tmp_path, monkeypatch) -> None:
    from lectos.gtk import pdfdoc

    doc = PdfDoc(PDF)
    assert doc.thumbnail(0, 40, 30) is doc.thumbnail(0, 40, 30)
    monkeypatch.setattr(pdfdoc, "THUMB_CACHE", 2)
    for width in (10, 11, 12, 13):
        doc.thumbnail(0, width, 10)
    assert len(doc._thumbs) == 2


# ---- ink input ----
class FakeDevice:
    def __init__(self, source: Gdk.InputSource) -> None:
        self.source = source

    def get_source(self) -> Gdk.InputSource:
        return self.source


class FakeTool:
    def __init__(self, kind: Gdk.DeviceToolType) -> None:
        self.kind = kind

    def get_tool_type(self) -> Gdk.DeviceToolType:
        return self.kind


class FakeGesture:
    def __init__(self, *, pressure: float | None = 0.5, tool=None, device=None, start=(50.0, 50.0)) -> None:
        self.pressure, self.tool, self.device, self.start = pressure, tool, device, start

    def get_device_tool(self):
        return self.tool

    def get_axis(self, _axis: Gdk.AxisUse) -> tuple[bool, float]:
        return (self.pressure is not None, self.pressure or 0.0)

    def get_current_event_device(self):
        return self.device

    def get_start_point(self) -> tuple[bool, float, float]:
        return True, self.start[0], self.start[1]


@pytest.fixture
def pen(rig):
    area = Gtk.DrawingArea()
    area.get_width = lambda: 400
    area.get_height = lambda: 300
    return InkInput(area, rig.core.stage, rig.core.ink, lambda: 0), rig.core.ink, rig.core.stage


def strokes(ink, stage) -> int:
    return len(ink.layers.get(stage.layer(0), []))


def test_a_stylus_draws_with_its_pressure_and_its_eraser_end_erases(pen) -> None:
    inp, ink, stage = pen
    inp._stylus_down(FakeGesture(pressure=0.8), 100.0, 100.0)
    inp._stylus_motion(FakeGesture(pressure=None), 120.0, 110.0)
    inp._up()
    assert strokes(ink, stage) == 1
    eraser = FakeGesture(tool=FakeTool(Gdk.DeviceToolType.ERASER), pressure=None)
    inp._stylus_down(eraser, 100.0, 100.0)
    inp._stylus_motion(eraser, 120.0, 110.0)
    inp._up()
    assert strokes(ink, stage) == 0
    inp._up()  # nothing in progress: harmless


def test_the_mouse_draws_only_when_asked_and_never_over_a_pen(pen) -> None:
    inp, ink, stage = pen
    mouse = FakeGesture(device=FakeDevice(Gdk.InputSource.MOUSE))
    inp._mouse_begin(mouse, 10.0, 10.0)
    inp._mouse_update(mouse, 5.0, 5.0)
    assert strokes(ink, stage) == 0
    ink.tool.mouse_draw = True
    inp._mouse_begin(mouse, 60.0, 60.0)
    inp._mouse_update(mouse, 20.0, 10.0)
    inp._up()
    assert strokes(ink, stage) == 1
    nopen = FakeGesture(device=FakeDevice(Gdk.InputSource.PEN))
    inp._mouse_begin(nopen, 10.0, 10.0)
    inp._mouse_update(nopen, 5.0, 5.0)
    assert strokes(ink, stage) == 1
    inp._mouse_begin(FakeGesture(device=None), 70.0, 70.0)  # unknown device counts as a mouse
    inp._up()
    assert strokes(ink, stage) == 2


# ---- projector window ----
@pytest.fixture
def window(rig, application):
    w = ProjectorWindow(application, rig.core.stage, rig.core.ink, None, config.Blackout())
    yield w
    w.destroy()


def test_the_projector_draws_the_slide_or_black(window) -> None:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 120)
    window._draw(None, cairo.Context(surface), 200, 120)
    surface.flush()
    assert any(surface.get_data())
    window.deck.blackout = True
    black = cairo.ImageSurface(cairo.FORMAT_RGB24, 20, 20)
    window._draw(None, cairo.Context(black), 20, 20)
    black.flush()
    assert not any(bytes(black.get_data())[i] for i in range(0, 1600, 4) for i in (i, i + 1, i + 2))


def test_projector_keys_drive_the_deck(window) -> None:
    deck = window.deck
    assert window._on_key(Gdk.KEY_Right) is True
    assert window._on_key(Gdk.KEY_space) is True
    assert window._on_key(Gdk.KEY_Left) is True
    assert deck.page == 1
    assert window._on_key(Gdk.KEY_b) is True
    assert deck.blackout is True
    window._on_key(Gdk.KEY_b)
    window.ink.add_stroke = None  # c clears the page's layer
    assert window._on_key(Gdk.KEY_c) is True
    assert window._on_key(Gdk.KEY_f) is True
    assert window._on_key(Gdk.KEY_F11) is True
    assert window._on_key(Gdk.KEY_Escape) is True
    assert window._on_key(Gdk.KEY_q) is False


def test_the_projector_goes_fullscreen_on_a_monitor_or_anywhere(window) -> None:
    window.set_fullscreen(True)
    window.set_fullscreen(False)
    window.monitor = pick_monitor(None)[0]
    window.set_fullscreen(True)
    window.set_fullscreen(False)


def test_a_configured_blackout_screen_is_shown_only_during_blackout(rig, application, tmp_path) -> None:
    cover = tmp_path / "cover.png"
    cairo.ImageSurface(cairo.FORMAT_ARGB32, 8, 8).write_to_png(str(cover))
    for blackout in (
        config.Blackout(image=cover, text="back soon"),
        config.Blackout(text="only text"),
        config.Blackout(image=cover),
    ):
        w = ProjectorWindow(application, rig.core.stage, rig.core.ink, None, blackout)
        assert w.standby is not None
        assert w.standby.get_visible() is False
        w.deck.blackout = True
        w._on_deck()
        assert w.standby.get_visible() is True
        w.deck.blackout = False
        w.destroy()


def test_the_window_projector_adapts_the_window(window) -> None:
    proj = WindowProjector(window)
    proj.goto(3)
    proj.fullscreen(False)
    assert proj.is_fullscreen() is False
    assert proj.caps == GTK_CAPS
    proj.stop()


# ---- app ----
def test_the_core_follows_options_and_projector_capabilities(tmp_path, monkeypatch) -> None:
    options = config.Options()
    core = build_core(PDF, frozenset(), options)
    assert core.deck.board is False
    assert core.stage.deck is core.deck
    core.ink.dirty = True
    save_ink(PDF, core.ink)
    assert core.ink.dirty is False
    save_ink(PDF, core.ink)  # clean: nothing to write


def test_ink_that_cannot_be_saved_stays_dirty(rig, monkeypatch, capsys) -> None:
    from lectos import state

    def refuse(*_a: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(state, "save", refuse)
    rig.core.ink.dirty = True
    save_ink(PDF, rig.core.ink)
    assert rig.core.ink.dirty is True
    assert "cannot save ink: disk full" in capsys.readouterr().err
    app_module._save(PDF, rig.console)
    assert "cannot save state: disk full" in capsys.readouterr().err


def test_monitors_are_chosen_by_index_or_default() -> None:
    _chosen, count = pick_monitor(None)
    assert count >= 1
    assert pick_monitor(count + 3)[0] is None
    assert pick_monitor(-5)[0] is None


def test_each_projector_kind_is_built(rig, application, monkeypatch) -> None:
    options = config.Options()
    assert isinstance(
        make_projector(application, rig.core, "none", options, PDF, windowed=True, monitor=None), NullProjector
    )
    started: list[str] = []

    class FakeZathura:
        def __init__(self, pdf: Path) -> None:
            self.pdf = pdf

        def start(self) -> None:
            started.append("start")

    monkeypatch.setattr(app_module, "Zathura", FakeZathura)
    z = make_projector(application, rig.core, "zathura", options, PDF, windowed=True, monitor=None)
    assert started == ["start"]
    assert getattr(z, "pdf") == PDF.resolve()  # noqa: B009
    proj = make_projector(application, rig.core, "gtk", options, PDF, windowed=True, monitor=None)
    assert getattr(proj, "window").get_visible()  # noqa: B009
    proj.stop()
    monkeypatch.setattr(app_module, "pick_monitor", lambda _i: (None, 2))
    many = make_projector(application, rig.core, "gtk", options, PDF, windowed=False, monitor=None)
    many.stop()


def run_app(monkeypatch, wait_for, **kwargs):
    """Run ``app.run`` for real, closing the console as soon as it is up."""
    holder: dict[str, object] = {}
    real = app_module._open_console

    def opened(app, pdf, core, proj, *, notes, options):
        session = real(app, pdf, core, proj, notes=notes, options=options)
        holder["windows"] = app.get_windows()
        GLib.timeout_add(150, lambda: [w.close() for w in app.get_windows()] and False)
        return session

    monkeypatch.setattr(app_module, "_open_console", opened)
    monkeypatch.setattr(app_module, "POLL_MS", 40)
    monkeypatch.setattr(app_module, "SAVE_MS", 40)
    deck = kwargs.pop("pdf", PDF)
    status = app_module.run(deck, None, config.Options(), windowed=True, monitor=None, **kwargs)
    return status, holder


def test_the_application_runs_until_the_console_is_closed(monkeypatch, wait_for, capsys) -> None:
    status, holder = run_app(monkeypatch, wait_for, projector="gtk")
    assert status == 0
    assert holder["windows"]
    status, _ = run_app(monkeypatch, wait_for, projector="none")
    assert status == 0


def test_a_projector_that_cannot_start_ends_the_application(monkeypatch, wait_for, capsys) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise ProjectorError("no zathura")

    monkeypatch.setattr(app_module, "make_projector", boom)
    status = app_module.run(PDF, None, config.Options(), projector="zathura", windowed=True, monitor=None)
    assert status == 1
    assert "no zathura" in capsys.readouterr().err


def test_the_timers_reload_a_changed_pdf_and_save_what_changed(rig, tmp_path, monkeypatch) -> None:
    saved: list[object] = []
    monkeypatch.setattr(app_module, "_save", lambda *_a: saved.append(1))
    monkeypatch.setattr(app_module, "POLL_MS", 20)
    monkeypatch.setattr(app_module, "SAVE_MS", 20)
    refreshed = []
    rig.core.doc.refresh = lambda: refreshed.append(1) or True
    rig.console.dirty = True
    app_module._start_timers(PDF, rig.core, rig.console)
    GLib.timeout_add(150, lambda: False)
    ctx = GLib.MainContext.default()
    import time

    end = time.monotonic() + 0.2
    while time.monotonic() < end:
        ctx.iteration(False)
    assert refreshed
    assert saved


def test_without_slides_the_application_shows_the_start_window(monkeypatch, wait_for) -> None:
    shown: list[object] = []
    real = app_module.Launcher.show_start

    def watched(self) -> None:
        real(self)
        shown.extend(self.app.get_windows())
        GLib.timeout_add(150, lambda: [w.close() for w in self.app.get_windows()] and False)

    monkeypatch.setattr(app_module.Launcher, "show_start", watched)
    assert run_app(monkeypatch, wait_for, pdf=None, projector="none")[0] == 0
    assert [type(w).__name__ for w in shown] == ["StartWindow"]


def test_the_launcher_switches_to_other_slides_and_a_failing_projector_ends_it(rig, application, monkeypatch) -> None:
    launcher = app_module.Launcher(application, config.Options(), projector="none", windowed=True, monitor=None)
    launcher.begin(PDF, None)
    first = launcher.session
    assert first is not None
    assert first.console.opener == launcher.show_start
    seen = []
    real_start = app_module.StartWindow
    monkeypatch.setattr(
        app_module, "StartWindow", lambda app, on_start: seen.append(real_start(app, on_start)) or seen[-1]
    )
    launcher.show_start()
    seen[0].on_start(PDF, EXAMPLES / "notes.md")  # the user picked slides and notes
    second = launcher.session
    assert second is not None
    assert second is not first
    assert second.console.notes is not None
    second.finish()
    launcher.session = None
    seen[0].on_start(PDF, None)  # with nothing presented yet there is nothing to finish
    third = launcher.session
    assert third is not None
    third.finish()
    monkeypatch.setattr(
        app_module, "make_projector", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no projector"))
    )
    launcher.begin(PDF, None)
    assert launcher.failure == ["no projector"]


def test_bundled_icons_are_registered_once() -> None:
    from gi.repository import Gdk, Gtk

    app_module.register_icons()
    app_module.register_icons()
    theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
    assert list(theme.get_search_path()).count(str(app_module.ICON_DIR)) == 1
    assert theme.has_icon("lectos")
    assert theme.has_icon("lectos-projector")


def test_the_windows_say_which_one_they_are(rig, application) -> None:
    assert rig.console.get_title() == "lectos console - slides.pdf"
    assert rig.console.get_icon_name() == "lectos"
    window = ProjectorWindow(application, rig.core.stage, rig.core.ink, None, config.Blackout(), name="slides.pdf")
    assert window.get_title() == "lectos projector - slides.pdf"
    assert window.get_icon_name() == "lectos-projector"
    window.destroy()


def test_the_pointer_shows_what_the_mouse_will_do(pen) -> None:
    inp, ink, _stage = pen
    assert inp.area.get_cursor() is None
    ink.tool.mouse_draw = True
    ink.notify()
    assert inp.area.get_cursor().get_name() == "crosshair"
    ink.tool.eraser = True
    ink.notify()
    assert inp.area.get_cursor().get_name() == "cell"
    ink.tool.mouse_draw = False
    ink.notify()
    assert inp.area.get_cursor() is None
