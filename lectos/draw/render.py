"""Cairo drawing shared by both windows: fitting, strokes, laser dot, chalkboard. No GTK."""

from __future__ import annotations

import cairo

from lectos.model.ink import Stroke
from lectos.model.style import BOARD_STYLES, DEFAULT_BOARD, LaserStyle

BOARD_SIZE = (1600.0, 900.0)
ROUND_CAP = cairo.LINE_CAP_ROUND
PRESSURE_FLOOR = 0.3


def fit(pw: float, ph: float, width: float, height: float) -> tuple[float, float, float]:
    """Return (scale, x offset, y offset) centering a pw x ph page in the area."""
    scale = min(width / pw, height / ph)
    return scale, (width - pw * scale) / 2, (height - ph * scale) / 2


def hex_rgb(color: str) -> tuple[float, float, float]:
    """Convert ``#rrggbb`` to cairo's 0..1 triple."""
    return tuple(int(color[i : i + 2], 16) / 255 for i in (1, 3, 5))  # ty: ignore[invalid-return-type]


def draw_strokes(cr: cairo.Context, strokes: list[Stroke], scale: float) -> None:
    """Draw strokes in layer coordinates; ``scale`` keeps pen width constant on screen."""
    cr.set_line_cap(ROUND_CAP)
    for stroke in strokes:
        if stroke.alpha < 1.0:
            cr.push_group()  # one uniform translucency for the whole stroke, no darker joints
            _draw_stroke(cr, stroke, scale)
            cr.pop_group_to_source()
            cr.paint_with_alpha(stroke.alpha)
        else:
            _draw_stroke(cr, stroke, scale)


def _draw_stroke(cr: cairo.Context, stroke: Stroke, scale: float) -> None:
    cr.set_source_rgb(*hex_rgb(stroke.color))
    if len(stroke.points) == 1:
        x, y, p = stroke.points[0]
        cr.arc(x, y, stroke.width * (PRESSURE_FLOOR + p) / scale / 2, 0, 6.2832)
        cr.fill()
    for (x0, y0, _), (x1, y1, p1) in zip(stroke.points, stroke.points[1:], strict=False):
        cr.set_line_width(stroke.width * (PRESSURE_FLOOR + p1) / scale)
        cr.move_to(x0, y0)
        cr.line_to(x1, y1)
        cr.stroke()


def draw_laser(
    cr: cairo.Context, position: tuple[float, float], size: tuple[float, float], scale: float, look: LaserStyle
) -> None:
    """Draw the laser pointer at a fractional position of the page in the configured look."""
    x, y, r = position[0] * size[0], position[1] * size[1], look.size / scale
    rgb = hex_rgb(look.color)
    if look.halo:
        halo = cairo.RadialGradient(x, y, 0, x, y, r * 2.2)
        halo.add_color_stop_rgba(0, *rgb, 0.55)
        halo.add_color_stop_rgba(1, *rgb, 0.0)
        cr.set_source(halo)
        cr.arc(x, y, r * 2.2, 0, 6.2832)
        cr.fill()
    cr.set_source_rgb(*rgb)
    if look.style == "dot":
        cr.arc(x, y, r, 0, 6.2832)
        cr.fill()
        return
    cr.set_line_width(max(2.0, r / 3))
    if look.style == "ring":
        cr.arc(x, y, r, 0, 6.2832)
    else:  # cross
        cr.move_to(x - r * 1.4, y)
        cr.line_to(x + r * 1.4, y)
        cr.move_to(x, y - r * 1.4)
        cr.line_to(x, y + r * 1.4)
    cr.stroke()


def draw_board(cr: cairo.Context, width: int, height: int, style: str = DEFAULT_BOARD) -> tuple[float, float, float]:
    """Paint black, then the chalkboard fitted and centered; leave the transform applied."""
    look = BOARD_STYLES.get(style, BOARD_STYLES[DEFAULT_BOARD])
    cr.set_source_rgb(0, 0, 0)
    cr.paint()
    scale, ox, oy = fit(*BOARD_SIZE, width, height)
    cr.translate(ox, oy)
    cr.scale(scale, scale)
    cr.set_source_rgb(*look.bg)
    cr.rectangle(0, 0, *BOARD_SIZE)
    cr.fill()
    if look.line is not None and look.spacing > 0:
        cr.set_source_rgb(*look.line)
        cr.set_line_width(1.5 / scale)
        for y in _steps(BOARD_SIZE[1], look.spacing):
            cr.move_to(0, y)
            cr.line_to(BOARD_SIZE[0], y)
        if look.grid:
            for x in _steps(BOARD_SIZE[0], look.spacing):
                cr.move_to(x, 0)
                cr.line_to(x, BOARD_SIZE[1])
        cr.stroke()
    return scale, ox, oy


def _steps(limit: float, spacing: float) -> list[float]:
    count = int(limit // spacing)
    return [spacing * i for i in range(1, count + 1) if spacing * i < limit]
