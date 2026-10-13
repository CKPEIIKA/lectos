"""Beamer notes: extract ``\\note{...}`` from a .tex file and map frames to PDF pages via the .nav file."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from lectos.notes.markdown import (
    MAX_NOTES_BYTES,
    MarkdownNotes,
    NotesError,
    NotesSource,
    Section,
    load_sections,
    replace_section,
)
from lectos.paths import write_atomic
from lectos.state import edits_path

_TOKEN_RE = re.compile(r"\\begin\s*\{frame\}|\\frame\b|\\frametitle\b|\\note\b")
_COMMENT_RE = re.compile(r"(?<!\\)%.*")
_FRAMEPAGES_RE = re.compile(r"\\beamer@framepages\s*\{(\d+)\}\{(\d+)\}")
_ITEM_RE = re.compile(r"\\item(\s*\[[^\]]*\])?[ \t]*")
_LIST_RE = re.compile(r"\\(?:begin|end)\s*\{(?:itemize|enumerate|description)\}(\s*\[[^\]]*\])?")
_WRAP_RE = re.compile(r"\\(textbf|alert|emph|textit|texttt)\s*\{([^{}]*)\}")
_DROP_RE = re.compile(r"\\(?:pause|newline|bigskip|medskip|smallskip)\b|\\vspace\*?\s*\{[^{}]*\}")
_WRAP_MARK = {"textbf": "**", "alert": "**", "emph": "*", "textit": "*", "texttt": "`"}
_SYMBOLS = (
    (re.compile(r"\\textbackslash\s*"), "\\"),
    (re.compile(r"\\textasciitilde\s*"), "~"),
    (re.compile(r"\\(?=[%&_#])"), ""),
)  # LaTeX text-mode escapes shown literally
_NESTING_PASSES = 3


@dataclass(frozen=True)
class Note:
    """A ``\\note`` and the zero-based frame it belongs to (-1 before any frame)."""

    frame: int
    text: str


@dataclass(frozen=True)
class Scan:
    """Notes, frame titles by index, and the number of frames found in the source."""

    notes: list[Note]
    titles: dict[int, str]
    frames: int


def _skip_space(text: str, pos: int) -> int:
    while pos < len(text) and text[pos] in " \t\r\n":
        pos += 1
    return pos


def _balanced(text: str, pos: int, open_: str = "{", close: str = "}") -> tuple[str, int] | None:
    """Read a balanced group starting at the first ``open_`` after whitespace; return (content, end)."""
    pos = _skip_space(text, pos)
    if text[pos : pos + 1] != open_:
        return None
    depth, start = 0, pos + 1
    while pos < len(text):
        if text[pos] == "\\":
            pos += 1  # skip the escaped character
        elif text[pos] in (open_, close):
            depth += 1 if text[pos] == open_ else -1
            if depth == 0:
                return text[start:pos], pos + 1
        pos += 1
    return None


def _skip_options(text: str, pos: int) -> int:
    """Skip any ``<...>`` and ``[...]`` option groups after a command."""
    for open_, close in (("<", ">"), ("[", "]")):
        group = _balanced(text, pos, open_, close)
        if group is not None:
            pos = group[1]
    return pos


def scan(tex: str) -> Scan:
    """Find frames, frame titles and notes in Beamer source, ignoring comments."""
    text = _COMMENT_RE.sub("", tex)
    notes: list[Note] = []
    titles: dict[int, str] = {}
    frame = -1
    pos = 0
    while (m := _TOKEN_RE.search(text, pos)) is not None:
        token, pos = m.group(0), m.end()
        starts_frame = token == "\\frame" or token.startswith("\\begin")
        frame += starts_frame
        group = _balanced(text, _skip_options(text, pos))
        if group is None or token == "\\frame":
            continue
        if token == "\\note":
            notes.append(Note(frame, group[0]))
            pos = group[1]
        else:  # \frametitle{..} or the title argument of \begin{frame}{..}
            titles.setdefault(frame, group[0])
    return Scan(notes, titles, frame + 1)


def frame_pages(nav: str) -> list[tuple[int, int]]:
    """First and last PDF page (one-based) of every frame, in order, from a ``.nav`` file."""
    return [(int(a), int(b)) for a, b in _FRAMEPAGES_RE.findall(nav)]


def to_markdown(raw: str) -> str:
    """Convert common LaTeX note markup to the light Markdown that ``markdown.parse`` understands."""
    text = raw
    for pattern, replacement in _SYMBOLS:
        text = pattern.sub(lambda _m, r=replacement: r, text)
    text = _LIST_RE.sub("", text)
    text = _ITEM_RE.sub("\n- ", text)
    text = _DROP_RE.sub("", text)
    for _ in range(_NESTING_PASSES):
        text = _WRAP_RE.sub(lambda m: f"{_WRAP_MARK[m.group(1)]}{m.group(2)}{_WRAP_MARK[m.group(1)]}", text)
    text = text.replace("\\\\", "\n")
    lines = [line.strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def sections(tex: str, nav: str | None) -> list[Section]:
    """One section per frame that has notes, tied to the frame's first page."""
    found = scan(tex)
    pages = frame_pages(nav) if nav else []
    grouped: dict[int, list[str]] = {}
    for note in found.notes:
        grouped.setdefault(note.frame, []).append(to_markdown(note.text))
    out: list[Section] = []
    for frame in sorted(grouped):
        slide = pages[frame][0] if 0 <= frame < len(pages) else (frame + 1 if frame >= 0 else None)
        title = to_markdown(found.titles[frame]) if frame in found.titles else ""
        body = "\n\n".join(t for t in grouped[frame] if t)
        out.append(Section(slide, (f"## {title}\n\n" if title else "") + body + "\n"))
    return out


class BeamerNotes:
    """Notes source reading ``\\note`` commands from a .tex file.

    Page numbers come from the first existing ``.nav`` among ``navs`` (Beamer writes it next
    to the .tex or PDF); without one, frame N is taken to be slide N (wrong with overlays).
    """

    def __init__(self, tex: Path, navs: list[Path], edits: Path | None = None) -> None:
        self.tex, self.navs, self.edits = tex, navs, edits

    def _nav(self) -> Path | None:
        return next((p for p in self.navs if p.exists()), None)

    def stamp(self) -> int:
        """Change marker: newest of the source and the page map."""
        times = [p.stat().st_mtime_ns for p in (self.tex, self._nav(), self.edits) if p is not None and p.exists()]
        return max(times, default=0)

    def load(self) -> list[Section]:
        """Read and convert the notes."""
        nav = self._nav()
        try:
            if self.tex.stat().st_size > MAX_NOTES_BYTES:
                raise NotesError(f"{self.tex} exceeds {MAX_NOTES_BYTES} bytes")
            tex = self.tex.read_text(encoding="utf-8", errors="replace")
            nav_text = nav.read_text(encoding="utf-8", errors="replace") if nav else None
        except OSError as exc:
            raise NotesError(f"cannot read {self.tex}: {exc}") from exc
        found = sections(tex, nav_text)
        if self.edits is not None and self.edits.exists():
            found = merge_edits(found, load_sections(self.edits))
        return found

    def save(self, slide: int, text: str) -> None:
        """Keep an edited slide's notes in the edits file; the .tex stays as it is."""
        if self.edits is None:
            raise NotesError("no place to keep edited notes")
        try:
            before = self.edits.read_text(encoding="utf-8") if self.edits.exists() else ""
            write_atomic(self.edits, replace_section(before, slide, text))
        except OSError as exc:
            raise NotesError(f"cannot write {self.edits}: {exc}") from exc


def merge_edits(base: list[Section], edits: list[Section]) -> list[Section]:
    """The extracted sections with the edited ones in place (new slides added), ordered by slide."""
    edited = {s.slide: s for s in edits if s.slide is not None}
    merged = [edited.pop(s.slide, s) if s.slide is not None else s for s in base]
    merged += edited.values()
    return sorted(merged, key=lambda s: (s.slide is not None, s.slide or 0))


def open_notes(notes: Path, pdf: Path) -> NotesSource:
    """Choose the notes source by file type: ``.tex`` is Beamer (edits are kept in the state folder), else Markdown."""
    if notes.suffix == ".tex":
        return BeamerNotes(notes, [notes.with_suffix(".nav"), pdf.with_suffix(".nav")], edits_path(pdf))
    return MarkdownNotes(notes)
