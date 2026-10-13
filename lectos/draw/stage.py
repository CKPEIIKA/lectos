"""What the audience sees: a slide or the chalkboard, plus its ink and the laser. Shared by both windows."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Protocol

import cairo

from lectos.draw import render
from lectos.model.deck import Deck
from lectos.model.ink import BOARD_LAYER, Ink, slide_layer
from lectos.model.style import LaserStyle

PNG_MIN_WIDTH = 1920  # pixels: an exported drawing layer is at least this wide


class Slides(Protocol):
    """The part of ``PdfDoc`` the stage needs."""

    def page_size(self, page: int) -> tuple[float, float]:
        """Width and height of the page in points."""

    def paint(self, cr: cairo.Context, page: int) -> None:
        """Paint the page in its own coordinate space."""

    def draw(self, cr: cairo.Context, page: int, width: int, height: int) -> tuple[float, float, float]:
        """Paint the page fitted to the area and return the fit used."""


class Stage:
    """Draws ``page`` as a slide, or the chalkboard when ``deck.board`` is on."""

    def __init__(self, doc: Slides, deck: Deck, ink: Ink, laser: LaserStyle | None = None) -> None:
        self.doc, self.deck, self.ink = doc, deck, ink
        self.laser = laser or LaserStyle()

    def layer(self, page: int) -> str:
        """Ink layer being shown for ``page``."""
        return BOARD_LAYER if self.deck.board else slide_layer(page)

    def size(self, page: int) -> tuple[float, float]:
        """Logical size of what is shown; ink and laser coordinates live in this space."""
        return render.BOARD_SIZE if self.deck.board else self.doc.page_size(page)

    def fit(self, page: int, width: int, height: int) -> tuple[float, float, float]:
        """Scale and offsets of what is shown inside an area."""
        return render.fit(*self.size(page), width, height)

    def draw(self, cr: cairo.Context, page: int, width: int, height: int) -> tuple[float, float, float]:
        """Paint the shown content with its ink and the laser dot; return the fit used."""
        fit = (
            render.draw_board(cr, width, height, self.deck.board_style)
            if self.deck.board
            else self.doc.draw(cr, page, width, height)
        )
        render.draw_strokes(cr, self.ink.strokes(self.layer(page)), fit[0])
        if self.deck.laser is not None:
            render.draw_laser(cr, self.deck.laser, self.size(page), fit[0], self.laser)
        return fit

    def to_layer(self, page: int, width: int, height: int, x: float, y: float) -> tuple[float, float]:
        """Convert widget coordinates to layer coordinates."""
        scale, ox, oy = self.fit(page, width, height)
        return (x - ox) / scale, (y - oy) / scale

    def to_fraction(self, page: int, width: int, height: int, x: float, y: float) -> tuple[float, float] | None:
        """Widget coordinates as fractions of the shown content, or None outside it."""
        lx, ly = self.to_layer(page, width, height, x, y)
        pw, ph = self.size(page)
        fx, fy = lx / pw, ly / ph
        return (fx, fy) if 0 <= fx <= 1 and 0 <= fy <= 1 else None

    def export_ink_png(self, path: Path, page: int) -> None:
        """Write the drawing layer of what is shown for ``page`` alone, on a transparent background."""
        width, height = self.size(page)
        scale = max(1.0, PNG_MIN_WIDTH / width)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, math.ceil(width * scale), math.ceil(height * scale))
        render.draw_strokes(cairo.Context(surface), self.ink.strokes(self.layer(page)), scale)
        surface.write_to_png(str(path))

    def export_pdf(self, path: Path) -> int:
        """Write every slide with its ink to a new PDF (plus the chalkboard if it has ink); returns the page count."""
        first = self.doc.page_size(0)
        surface = cairo.PDFSurface(str(path), *first)
        cr = cairo.Context(surface)
        pages = 0
        for page in range(self.deck.pages):
            surface.set_size(*self.doc.page_size(page))
            self.doc.paint(cr, page)
            render.draw_strokes(cr, self.ink.strokes(slide_layer(page)), 1.0)
            cr.show_page()
            pages += 1
        if self.ink.strokes(BOARD_LAYER):
            surface.set_size(*render.BOARD_SIZE)
            cr.save()
            render.draw_board(cr, int(render.BOARD_SIZE[0]), int(render.BOARD_SIZE[1]), self.deck.board_style)
            render.draw_strokes(cr, self.ink.strokes(BOARD_LAYER), 1.0)
            cr.restore()
            cr.show_page()
            pages += 1
        surface.finish()
        return pages
