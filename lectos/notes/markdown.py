"""Lecture notes: split on slide markers and parse light Markdown with LaTeX math into styled spans."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from lectos.paths import write_atomic

MAX_NOTES_BYTES = 4 * 1024 * 1024
_MARKER_RE = re.compile(r"^<!--\s*slide:\s*(\d+)\s*-->[ \t]*$", re.MULTILINE)
_MATH_RE = re.compile(
    r"\$\$(?P<d1>.+?)\$\$|\\\[(?P<d2>.+?)\\\]|(?<![\\$])\$(?![\s$])(?P<i>[^$\n]+?)(?<!\s)\$(?!\d)",
    re.DOTALL,
)
_EMPH_RE = re.compile(r"\*\*(?P<bold>.+?)\*\*|\*(?P<italic>[^*\n]+?)\*|`(?P<code>[^`\n]+?)`")
_HEADING_RE = re.compile(r"^(#{1,3}) +(.*)$")
_BULLET_RE = re.compile(r"^(\s*)[-*] +")


class NotesError(RuntimeError):
    """Raised when notes cannot be read."""


@dataclass(frozen=True)
class Section:
    """A run of notes. ``slide`` is one-based, or None before the first marker."""

    slide: int | None
    text: str


@dataclass(frozen=True)
class Span:
    """Styled text. ``style`` is '', h1-h3, bold, italic, code, math or display."""

    text: str
    style: str = ""


class NotesSource(Protocol):
    """Where notes come from: a Markdown file or Beamer ``\\note`` commands."""

    def stamp(self) -> int:
        """Value that changes whenever the notes may have changed."""

    def load(self) -> list[Section]:
        """Read the notes into sections."""

    def save(self, slide: int, text: str) -> None:
        """Replace the notes of one slide (one-based) with ``text``."""


class MarkdownNotes:
    """Notes read from a Markdown file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def stamp(self) -> int:
        """Modification time of the file."""
        return self.path.stat().st_mtime_ns

    def load(self) -> list[Section]:
        """Read the file."""
        return load_sections(self.path)

    def save(self, slide: int, text: str) -> None:
        """Rewrite the file with this slide's notes replaced."""
        try:
            write_atomic(self.path, replace_section(self.path.read_text(encoding="utf-8"), slide, text))
        except OSError as exc:
            raise NotesError(f"cannot write {self.path}: {exc}") from exc


def split_markdown(text: str) -> list[tuple[int | None, str]]:
    """Split at ``<!-- slide: N -->`` markers, dropping empty chunks."""
    parts: list[tuple[int | None, str]] = []
    slide: int | None = None
    last = 0
    for match in _MARKER_RE.finditer(text):
        parts.append((slide, text[last : match.start()]))
        slide, last = int(match.group(1)), match.end()
    parts.append((slide, text[last:]))
    return [(s, chunk) for s, chunk in parts if chunk.strip()]


def replace_section(text: str, slide: int, body: str) -> str:
    """``text`` with the notes of ``slide`` replaced by ``body``; a slide without notes gets a new marker at the end."""
    clean = body.strip("\n") + "\n"
    matches = list(_MARKER_RE.finditer(text))
    for i, match in enumerate(matches):
        if int(match.group(1)) == slide:
            following = matches[i + 1].start() if i + 1 < len(matches) else None
            tail = "" if following is None else "\n" + text[following:]
            return f"{text[: match.end()]}\n{clean}{tail}"
    gap = "" if not text or text.endswith("\n") else "\n"
    return f"{text}{gap}\n<!-- slide: {slide} -->\n{clean}"


def load_sections(path: Path) -> list[Section]:
    """Read the notes file into sections."""
    try:
        if path.stat().st_size > MAX_NOTES_BYTES:
            raise NotesError(f"{path} exceeds {MAX_NOTES_BYTES} bytes")
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise NotesError(f"cannot read {path}: {exc}") from exc
    return [Section(slide, chunk) for slide, chunk in split_markdown(text)]


def _inline(text: str) -> list[Span]:
    spans: list[Span] = []
    last = 0
    for m in _EMPH_RE.finditer(text):
        spans.append(Span(text[last : m.start()]))
        style = m.lastgroup or ""
        spans.append(Span(m.group(style), style))
        last = m.end()
    spans.append(Span(text[last:]))
    return spans


def _plain(text: str) -> list[Span]:
    spans: list[Span] = []
    for line in text.splitlines(keepends=True):
        heading = _HEADING_RE.match(line.rstrip("\n"))
        if heading:
            spans.append(Span(heading.group(2) + ("\n" if line.endswith("\n") else ""), f"h{len(heading.group(1))}"))
        else:
            spans += _inline(_BULLET_RE.sub(lambda m: f"{m.group(1)}• ", line))
    return spans


def parse(text: str) -> list[Span]:
    """Turn Markdown into spans; math spans carry the bare TeX in ``text``."""
    spans: list[Span] = []
    last = 0
    for m in _MATH_RE.finditer(text):
        spans += _plain(text[last : m.start()])
        display = m.group("i") is None
        spans.append(Span((m.group("d1") or m.group("d2") or m.group("i")).strip(), "display" if display else "math"))
        last = m.end()
    spans += _plain(text[last:])
    return [s for s in spans if s.text]
