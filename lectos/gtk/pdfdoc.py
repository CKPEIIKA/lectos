"""PDF access through Poppler: slides (or the slide half of notes pages), links, annotations, text, reloads."""

from __future__ import annotations

from pathlib import Path

import cairo
import gi

gi.require_version("Poppler", "0.18")
from gi.repository import GLib, Poppler

from lectos.model.links import Link
from lectos.notes.markdown import NotesError, Section

THUMB_CACHE = 256
SPLIT_MIN_RATIO = 2.4  # width / height from which a page is taken as slide plus notes side by side
NOTE_ANNOTATIONS = (Poppler.AnnotType.TEXT, Poppler.AnnotType.FREE_TEXT)


class PdfDoc:
    """An open PDF that can be reopened when the file changes.

    Pages that hold the slide and its notes side by side (Beamer's ``show notes on second screen``) are
    split: every method here sees only the slide half, ``draw_notes`` shows the other one.
    """

    def __init__(self, path: Path, notes_pages: str = "auto") -> None:
        self.path = path.resolve()
        self._requested = notes_pages
        self._mtime = 0
        self._doc = self._open()
        self._texts: tuple[str, ...] | None = None
        self.version = 0  # bumps whenever the file is reopened, so caches keyed on it go stale
        self._thumbs: dict[tuple[int, int, int, int], cairo.ImageSurface] = {}
        self._links: dict[int, list[Link]] = {}
        self._annotations: dict[int, list[str]] | None = None
        self.notes_side = self._resolve_split()

    def _open(self) -> Poppler.Document:
        self._mtime = self.path.stat().st_mtime_ns
        return Poppler.Document.new_from_file(self.path.as_uri(), None)

    def _resolve_split(self) -> str:
        """Which side of every page holds the notes ('' when pages are plain slides)."""
        if self._requested in ("left", "right"):
            return self._requested
        if self._requested == "none" or self.pages == 0:
            return ""
        width, height = self._doc.get_page(0).get_size()
        return "right" if width / height >= SPLIT_MIN_RATIO else ""  # Beamer's default side

    @property
    def pages(self) -> int:
        """Number of pages."""
        return self._doc.get_n_pages()

    def refresh(self) -> bool:
        """Reopen if the file changed; return True when it did."""
        try:
            if self.path.stat().st_mtime_ns == self._mtime:
                return False
            self._doc = self._open()
        except (OSError, GLib.Error):
            return False  # a compiler may be mid-write; try again on the next poll
        self._texts = None
        self._annotations = None
        self.version += 1
        self._thumbs.clear()
        self._links.clear()
        self.notes_side = self._resolve_split()
        return True

    def _full_size(self, page: int) -> tuple[float, float]:
        return self._doc.get_page(page).get_size()

    def _slide_x(self, page: int) -> float:
        """Where the slide half starts on the full page."""
        return self._full_size(page)[0] / 2 if self.notes_side == "left" else 0.0

    def page_size(self, page: int) -> tuple[float, float]:
        """Width and height of the slide in points."""
        width, height = self._full_size(page)
        return (width / 2 if self.notes_side else width), height

    def fit(self, page: int, width: int, height: int) -> tuple[float, float, float]:
        """Return (scale, x offset, y offset) centering the slide in the area."""
        pw, ph = self.page_size(page)
        scale = min(width / pw, height / ph)
        return scale, (width - pw * scale) / 2, (height - ph * scale) / 2

    def draw(self, cr, page: int, width: int, height: int) -> tuple[float, float, float]:
        """Paint black, then the slide fitted and centered; return the fit used."""
        cr.set_source_rgb(0, 0, 0)
        cr.paint()
        fit = self.fit(page, width, height)
        scale, ox, oy = fit
        cr.translate(ox, oy)
        cr.scale(scale, scale)
        self.paint(cr, page)
        return fit

    def paint(self, cr: cairo.Context, page: int) -> None:
        """Paint the slide onto its own coordinate space (white paper, then the content), without fitting."""
        pw, ph = self.page_size(page)
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(0, 0, pw, ph)
        cr.fill()
        self._render_half(cr, page, self._slide_x(page), pw, ph)

    def draw_notes(self, cr, page: int, width: int, height: int) -> None:
        """Paint the notes half of the page fitted into the area (nothing without notes pages)."""
        if not self.notes_side:
            return
        pw, ph = self.page_size(page)
        scale = min(width / pw, height / ph)
        cr.translate((width - pw * scale) / 2, (height - ph * scale) / 2)
        cr.scale(scale, scale)
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(0, 0, pw, ph)
        cr.fill()
        self._render_half(cr, page, pw if self.notes_side == "right" else 0.0, pw, ph)

    def _render_half(self, cr: cairo.Context, page: int, x: float, width: float, height: float) -> None:
        cr.save()
        cr.rectangle(0, 0, width, height)
        cr.clip()
        cr.translate(-x, 0)
        self._doc.get_page(page).render(cr)
        cr.restore()

    def thumbnail(self, page: int, width: int, height: int) -> cairo.ImageSurface:
        """The page fitted into width x height, rendered once and cached until the file changes."""
        key = (page, width, height, self.version)
        surface = self._thumbs.get(key)
        if surface is None:
            if len(self._thumbs) >= THUMB_CACHE:
                self._thumbs.pop(next(iter(self._thumbs)))
            surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
            self.draw(cairo.Context(surface), page, width, height)
            self._thumbs[key] = surface
        return surface

    def texts(self) -> tuple[str, ...]:
        """Text of every slide, extracted once per file version."""
        if self._texts is None:
            self._texts = tuple(self._slide_text(i) for i in range(self.pages))
        return self._texts

    def _slide_text(self, page: int) -> str:
        poppler_page = self._doc.get_page(page)
        if not self.notes_side:
            return poppler_page.get_text() or ""
        width, height = self._full_size(page)
        left = self._slide_x(page)
        area = Poppler.Rectangle()
        area.x1, area.y1, area.x2, area.y2 = left, 0.0, left + width / 2, height
        return poppler_page.get_text_for_area(area) or ""

    def _on_slide(self, page: int, x1: float, x2: float) -> bool:
        left = self._slide_x(page)
        return not self.notes_side or left <= (x1 + x2) / 2 <= left + self.page_size(page)[0]

    def links(self, page: int) -> list[Link]:
        """Clickable areas of the slide, in slide points with the origin top-left."""
        if page not in self._links:
            self._links[page] = self._read_links(page)
        return self._links[page]

    def _read_links(self, page: int) -> list[Link]:
        height = self.page_size(page)[1]
        left = self._slide_x(page)
        found = []
        for mapping in self._doc.get_page(page).get_link_mapping():
            area = mapping.area
            target = self._target(mapping.action)
            if target is None or not self._on_slide(page, area.x1, area.x2):
                continue
            found.append(
                Link(area.x1 - left, height - area.y2, area.x2 - area.x1, area.y2 - area.y1, target[0], target[1])
            )
        return found

    def _target(self, action: Poppler.Action) -> tuple[int | None, str] | None:
        """(page, address) a link action leads to; None for actions lectos does not follow."""
        if action.type == Poppler.ActionType.URI:
            return None, action.uri.uri
        if action.type != Poppler.ActionType.GOTO_DEST:
            return None
        dest = action.goto_dest.dest
        if dest.type == Poppler.DestType.NAMED:
            dest = self._doc.find_dest(dest.named_dest)
        if dest is None or not 1 <= dest.page_num <= self.pages:
            return None
        return dest.page_num - 1, ""

    def annotations(self) -> dict[int, list[str]]:
        """Text of the note annotations on each slide (zero-based page), read once per file version."""
        if self._annotations is None:
            self._annotations = {}
            for page in range(self.pages):
                texts = self._page_annotations(page)
                if texts:
                    self._annotations[page] = texts
        return self._annotations

    def _page_annotations(self, page: int) -> list[str]:
        texts = []
        for mapping in self._doc.get_page(page).get_annot_mapping():
            text = (mapping.annot.get_contents() or "").strip()
            if (
                text
                and mapping.annot.get_annot_type() in NOTE_ANNOTATIONS
                and self._on_slide(page, mapping.area.x1, mapping.area.x2)
            ):
                texts.append(text)
        return texts


class AnnotationNotes:
    """Notes taken from the text annotations inside the PDF (read only)."""

    def __init__(self, doc: PdfDoc) -> None:
        self.doc = doc

    def stamp(self) -> int:
        """Changes when the PDF is reopened."""
        return self.doc.version

    def load(self) -> list[Section]:
        """One section per slide that has annotations."""
        return [Section(page + 1, "\n\n".join(texts) + "\n") for page, texts in sorted(self.doc.annotations().items())]

    def save(self, slide: int, text: str) -> None:
        """Annotations are read from the PDF and cannot be edited here."""
        raise NotesError("notes taken from PDF annotations are read only")
