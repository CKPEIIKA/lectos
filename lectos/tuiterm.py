"""Raw terminal access: key decoding, alternate screen, frame drawing. Standard library only."""

from __future__ import annotations

import codecs
import os
import select
import shutil
import sys
import termios
import tty
from types import TracebackType

READ_BYTES = 256
_CSI = {
    "A": "Up", "B": "Down", "C": "Right", "D": "Left", "H": "Home", "F": "End", "Z": "BackTab",
}  # fmt: skip
_TILDE = {"1": "Home", "3": "Delete", "4": "End", "5": "PageUp", "6": "PageDown", "7": "Home", "8": "End"}
_CONTROL = {"\r": "Enter", "\n": "Enter", "\t": "Tab", "\x7f": "Backspace", "\x08": "Backspace", "\x03": "C-c"}
ENTER_SCREEN = "\x1b[?1049h\x1b[?25l\x1b[2J"
LEAVE_SCREEN = "\x1b[?25h\x1b[?1049l"


def _keys(text: str) -> list[str]:
    keys: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        if char != "\x1b":
            keys.append(_CONTROL.get(char, char))
            i += 1
        elif text[i + 1 : i + 2] in ("[", "O"):
            j = i + 2
            while j < len(text) and (text[j].isdigit() or text[j] == ";"):
                j += 1
            final = text[j : j + 1]
            code = text[i + 2 : j]
            keys.append(_TILDE.get(code, "") if final == "~" else _CSI.get(final, ""))
            i = j + 1
        else:
            keys.append("Esc")
            i += 1
    return [k for k in keys if k]


class KeyDecoder:
    """Turns raw terminal bytes into key names; a UTF-8 character split across two reads is kept whole."""

    def __init__(self) -> None:
        self._utf8 = codecs.getincrementaldecoder("utf-8")(errors="ignore")

    def feed(self, data: bytes) -> list[str]:
        """Decode one chunk: plain characters, or Up, PageDown, Enter, Esc, C-c, ..."""
        return _keys(self._utf8.decode(data))


def decode(data: bytes) -> list[str]:
    """Decode a complete chunk of terminal input (use ``KeyDecoder`` for a stream)."""
    return _keys(data.decode("utf-8", errors="ignore"))


class Terminal:
    """Context manager: raw mode on the alternate screen; restores the terminal on exit."""

    def __init__(self) -> None:
        self._fd = sys.stdin.fileno()
        self._saved: list | None = None
        self._decoder = KeyDecoder()

    def __enter__(self) -> Terminal:
        self._saved = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        mode = termios.tcgetattr(self._fd)
        mode[3] &= ~termios.ISIG  # Ctrl-C is delivered as a key so the console can save and quit cleanly
        termios.tcsetattr(self._fd, termios.TCSADRAIN, mode)
        sys.stdout.write(ENTER_SCREEN)
        sys.stdout.flush()
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        sys.stdout.write(LEAVE_SCREEN)
        sys.stdout.flush()
        if self._saved is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)

    @staticmethod
    def size() -> tuple[int, int]:
        """Current (columns, rows)."""
        size = shutil.get_terminal_size((80, 24))
        return size.columns, size.lines

    def read_keys(self, timeout: float) -> list[str]:
        """Wait up to ``timeout`` seconds for input; return the decoded keys (possibly none)."""
        ready, _, _ = select.select([self._fd], [], [], timeout)
        return self._decoder.feed(os.read(self._fd, READ_BYTES)) if ready else []

    @staticmethod
    def draw(lines: list[str]) -> None:
        """Replace the screen with ``lines`` (already clipped to the terminal width)."""
        body = "\x1b[K\r\n".join(lines)
        sys.stdout.write(f"\x1b[H{body}\x1b[K\x1b[J")
        sys.stdout.flush()
