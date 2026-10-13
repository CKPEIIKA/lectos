import os
import pty
import sys
import termios
from collections.abc import Iterator

import pytest

from lectos.term import tuiterm
from lectos.term.tuiterm import Terminal


@pytest.fixture
def pty_stdin(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[int, int]]:
    """Standard input on a real pseudo-terminal: (master fd to type into, slave fd the program reads)."""
    master, slave = pty.openpty()
    stdin = os.fdopen(slave, "r", closefd=False)
    monkeypatch.setattr(sys, "stdin", stdin)
    yield master, slave
    stdin.close()
    os.close(master)
    os.close(slave)


def test_context_manager_switches_to_the_alternate_screen_and_back(
    pty_stdin: tuple[int, int], capsys: pytest.CaptureFixture[str]
) -> None:
    _master, slave = pty_stdin
    before = termios.tcgetattr(slave)
    with Terminal():
        inside = termios.tcgetattr(slave)
        assert inside[3] & termios.ISIG == 0  # Ctrl-C arrives as a key
        assert inside[3] & termios.ICANON == 0
        assert capsys.readouterr().out == tuiterm.ENTER_SCREEN
    assert termios.tcgetattr(slave) == before
    assert capsys.readouterr().out == tuiterm.LEAVE_SCREEN


def test_read_keys_waits_for_input_and_decodes_it(pty_stdin: tuple[int, int]) -> None:
    master, _slave = pty_stdin
    with Terminal() as terminal:
        assert terminal.read_keys(0.05) == []  # nothing typed: times out
        os.write(master, b"l\x1b[Aq")
        assert terminal.read_keys(1.0) == ["l", "Up", "q"]


def test_a_utf8_character_split_across_reads_is_kept(pty_stdin: tuple[int, int]) -> None:
    master, _slave = pty_stdin
    data = "я".encode()
    with Terminal() as terminal:
        os.write(master, data[:1])
        assert terminal.read_keys(1.0) == []
        os.write(master, data[1:])
        assert terminal.read_keys(1.0) == ["я"]


def test_draw_replaces_the_screen_with_the_given_lines(
    pty_stdin: tuple[int, int], capsys: pytest.CaptureFixture[str]
) -> None:
    with Terminal() as terminal:
        capsys.readouterr()
        terminal.draw(["one", "two"])
        assert capsys.readouterr().out == "\x1b[Hone\x1b[K\r\ntwo\x1b[K\x1b[J"


def test_size_and_exit_without_enter(monkeypatch: pytest.MonkeyPatch, pty_stdin: tuple[int, int]) -> None:
    monkeypatch.setattr(tuiterm.shutil, "get_terminal_size", lambda _default: os.terminal_size((101, 31)))
    terminal = Terminal()
    assert terminal.size() == (101, 31)
    terminal.__exit__(None, None, None)  # never entered: restores nothing, must not raise
