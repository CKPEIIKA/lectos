import os
import pty
import signal
import sys
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from conftest import EXAMPLES
from gi.repository import GLib

from lectos import config
from lectos.gtk import tuiglib
from lectos.term.tui import Tui

PDF = EXAMPLES / "slides.pdf"


@pytest.fixture
def typed(monkeypatch: pytest.MonkeyPatch) -> Iterator[int]:
    """Standard input on a pseudo-terminal; yields the master fd that stands for the keyboard."""
    master, slave = pty.openpty()
    stdin = os.fdopen(slave, "r", closefd=False)
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(tuiglib, "TICK_MS", 40)
    yield master
    stdin.close()
    os.close(master)
    os.close(slave)


def run(*, fullscreen: bool = False) -> int:
    return tuiglib.run(PDF, None, config.Options(), windowed=True, monitor=None, fullscreen=fullscreen)


def test_typing_quit_ends_the_console_and_closes_the_projector(typed: int) -> None:
    GLib.timeout_add(400, lambda: os.write(typed, b":q\r") and False)
    assert run(fullscreen=True) == 0


def test_ctrl_c_saves_and_quits(typed: int) -> None:
    GLib.timeout_add(400, lambda: os.kill(os.getpid(), signal.SIGINT) and False)
    assert run() == 0


def test_the_tick_notices_a_console_that_stopped_by_itself(typed: int, monkeypatch: pytest.MonkeyPatch) -> None:
    made = []
    real: Callable[..., Tui] = tuiglib.make_tui

    def capture(*args: Any, **kwargs: Any) -> Tui:
        made.append(real(*args, **kwargs))
        return made[-1]

    monkeypatch.setattr(tuiglib, "make_tui", capture)
    GLib.timeout_add(400, lambda: setattr(made[0], "running", False) and False)
    assert run() == 0


def test_a_console_that_cannot_start_reports_why(typed: int, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    def refuse(*_a, **_k) -> None:
        raise RuntimeError("no display for the projector")

    monkeypatch.setattr(tuiglib, "make_tui", refuse)
    assert run() == 1
    assert "no display for the projector" in capsys.readouterr().err
