"""Terminal text helpers: ANSI styling of note spans, word wrapping, and clipping to a width."""

from __future__ import annotations

import re
from dataclasses import dataclass

from lectos.notes.markdown import Span
from lectos.notes.unimath import to_unicode

RESET = "\x1b[0m"
STYLES = {
    "bold": "\x1b[1m", "italic": "\x1b[3m", "code": "\x1b[36m", "math": "\x1b[33m", "display": "\x1b[33m",
    "h1": "\x1b[1;4m", "h2": "\x1b[1m", "h3": "\x1b[1;2m",
}  # fmt: skip
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_TOKEN_RE = re.compile(r"\n|[^\s]+")


def visible_len(text: str) -> int:
    """Number of printable cells in ``text`` (escape sequences count as zero)."""
    return len(_ANSI_RE.sub("", text))


def clip(text: str, width: int) -> str:
    """Cut ``text`` to ``width`` printable cells, keeping escape sequences and closing styles."""
    out: list[str] = []
    cells = 0
    pos = 0
    while pos < len(text) and cells < width:
        match = _ANSI_RE.match(text, pos)
        if match:
            out.append(match.group(0))
            pos = match.end()
        else:
            out.append(text[pos])
            cells += 1
            pos += 1
    return "".join(out) + (RESET if "\x1b" in text else "")


def pad(text: str, width: int) -> str:
    """Clip or pad ``text`` with spaces to exactly ``width`` printable cells."""
    clipped = clip(text, width)
    return clipped + " " * (width - visible_len(clipped))


@dataclass(frozen=True)
class _Word:
    text: str
    style: str


def _tokens(spans: list[Span]) -> list[_Word | None]:
    """Words with their style; None marks a hard line break. Display math sits on its own lines."""
    out: list[_Word | None] = []
    for span in spans:
        text = to_unicode(span.text) if span.style in ("math", "display") else span.text
        if span.style == "display" or span.style.startswith("h"):
            out.append(None)
        out.extend(None if tok == "\n" else _Word(tok, span.style) for tok in _TOKEN_RE.findall(text))
        if span.style == "display":
            out.append(None)
    return out


def _render(words: list[_Word]) -> str:
    return " ".join(f"{STYLES[w.style]}{w.text}{RESET}" if w.style in STYLES else w.text for w in words)


class _Lines:
    """Accumulates words into lines no wider than ``width``."""

    def __init__(self, width: int) -> None:
        self.width = width
        self.lines: list[str] = []
        self.current: list[_Word] = []
        self.length = 0

    def flush(self) -> None:
        """End the current line; at a hard break with nothing pending, add one blank line."""
        if self.current:
            self.lines.append(_render(self.current))
        elif self.lines and self.lines[-1] != "":
            self.lines.append("")
        self.current, self.length = [], 0

    def add(self, word: _Word) -> None:
        """Append a word, starting a new line when it does not fit."""
        extra = len(word.text) + (1 if self.current else 0)
        if self.current and self.length + extra > self.width:
            self.flush()
            extra = len(word.text)
        self.current.append(word)
        self.length += extra

    def finish(self) -> list[str]:
        """The wrapped lines without trailing blanks."""
        if self.current:
            self.lines.append(_render(self.current))
        while self.lines and self.lines[-1] == "":
            self.lines.pop()
        return self.lines


def wrap(spans: list[Span], width: int) -> list[str]:
    """Wrap styled spans into ANSI lines of at most ``width`` cells. Single blank lines are kept."""
    lines = _Lines(width)
    for token in _tokens(spans):
        if token is None:
            lines.flush()
        else:
            lines.add(token)
    return lines.finish()
