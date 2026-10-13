"""PDF access through Poppler: page sizes, drawing onto Cairo, text for search, reload on change."""

from __future__ import annotations

from pathlib import Path

import cairo
import gi

gi.require_version("Poppler", "0.18")
from gi.repository import GLib, Poppler

THUMB_CACHE = 256


class PdfDoc:
    """An open PDF that can be reopened when the file changes."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self._mtime = 0
        self._doc = self._open()
        self._texts: tuple[str, ...] | None = None
        self.version = 0  # bumps whenever the file is reopened, so caches keyed on it go stale
        self._thumbs: dict[tuple[int, int, int, int], cairo.ImageSurface] = {}

    def _open(self) -> Poppler.Document:
        self._mtime = self.path.stat().st_mtime_ns
        return Poppler.Document.new_from_file(self.path.as_uri(), None)

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
        self.version += 1
        self._thumbs.clear()
        return True

    def page_size(self, page: int) -> tuple[float, float]:
        """Width and height of the page in points."""
        return self._doc.get_page(page).get_size()

    def fit(self, page: int, width: int, height: int) -> tuple[float, float, float]:
        """Return (scale, x offset, y offset) centering the page in the area."""
        pw, ph = self._doc.get_page(page).get_size()
        scale = min(width / pw, height / ph)
        return scale, (width - pw * scale) / 2, (height - ph * scale) / 2

    def draw(self, cr, page: int, width: int, height: int) -> tuple[float, float, float]:
        """Paint black, then the page fitted and centered; return the fit used."""
        cr.set_source_rgb(0, 0, 0)
        cr.paint()
        fit = self.fit(page, width, height)
        scale, ox, oy = fit
        pw, ph = self._doc.get_page(page).get_size()
        cr.translate(ox, oy)
        cr.scale(scale, scale)
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(0, 0, pw, ph)
        cr.fill()
        self._doc.get_page(page).render(cr)
        return fit

    def paint(self, cr: cairo.Context, page: int) -> None:
        """Paint the page onto its own coordinate space (white paper, then the content), without fitting."""
        pw, ph = self.page_size(page)
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(0, 0, pw, ph)
        cr.fill()
        self._doc.get_page(page).render(cr)

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
        """Text of every page, extracted once per file version."""
        if self._texts is None:
            self._texts = tuple(self._doc.get_page(i).get_text() or "" for i in range(self.pages))
        return self._texts
