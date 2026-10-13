"""Terminal console driving our GTK projector window, inside one GLib main loop."""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GLibUnix", "2.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gio, GLib, GLibUnix, Gtk

from lectos import state
from lectos.app import build_core, make_projector, save_ink
from lectos.config import Options
from lectos.projection import GTK_CAPS
from lectos.tui import Runner, Tui, make_tui
from lectos.tuiterm import Terminal

TICK_MS = 250


def _redirect_stderr(pdf: Path) -> int:
    """Send GTK's warnings to a log file so they cannot scribble over the terminal screen; returns the old fd."""
    log = state.state_path(pdf).with_suffix(".log")
    log.parent.mkdir(parents=True, exist_ok=True)
    saved = os.dup(2)
    os.dup2(os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), 2)
    return saved


def _wire(app: Gtk.Application, tui: Tui, runner: Runner, terminal: Terminal) -> None:
    """Connect the terminal's input, a periodic tick and SIGINT to the GLib main loop."""
    app.hold()  # the console, not the projector window, decides when to quit

    def finish() -> bool:
        runner.save()
        terminal.__exit__(None, None, None)
        app.release()
        app.quit()
        return False

    def on_input(_fd: int, _cond: GLib.IOCondition) -> bool:
        runner.step(terminal.read_keys(0))
        return finish() if not tui.running else True

    def on_tick() -> bool:
        runner.step([])
        return finish() if not tui.running else True

    GLib.io_add_watch(sys.stdin.fileno(), GLib.PRIORITY_DEFAULT, GLib.IOCondition.IN, on_input)
    GLib.timeout_add(TICK_MS, on_tick)
    GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, finish)


def run(
    pdf: Path, notes: Path | None, options: Options, *, windowed: bool, monitor: int | None, fullscreen: bool
) -> int:
    """Open our GTK projector window and run the terminal console until it quits."""
    app = Gtk.Application(
        application_id="org.lectos.tui", flags=Gio.ApplicationFlags.NON_UNIQUE
    )  # several decks can run at once
    failure: list[str] = []
    saved_stderr = _redirect_stderr(pdf)

    def activate(app: Gtk.Application) -> None:
        core = build_core(pdf, GTK_CAPS, options)
        try:
            projector = make_projector(app, core, "gtk", options, pdf, windowed=windowed, monitor=monitor)
            tui = make_tui(pdf, notes, options, projector, deck=core.deck, ink=core.ink, stage=core.stage)
        except RuntimeError as exc:
            failure.append(str(exc))
            return
        terminal = Terminal()
        terminal.__enter__()
        runner = Runner(tui, terminal, pdf, extra_save=lambda: save_ink(pdf, core.ink))
        if fullscreen:
            tui.execute("fullscreen on")
        _wire(app, tui, runner, terminal)
        runner.step([])

    app.connect("activate", activate)
    status = app.run([sys.argv[0]])
    os.dup2(saved_stderr, 2)
    if failure:
        print(f"lectos: {failure[0]}", file=sys.stderr)
        return 1
    return status
