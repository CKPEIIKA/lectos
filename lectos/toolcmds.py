"""Pen, board and laser settings as commands that return a message. Shared by both consoles; no GUI code."""

from __future__ import annotations

from lectos.deck import Deck
from lectos.i18n import noop, tr
from lectos.ink import (
    COLORS,
    MAX_ERASER_RADIUS,
    MAX_HIGHLIGHT_ALPHA,
    MAX_PEN_WIDTH,
    MAX_SMOOTHING,
    MIN_ERASER_RADIUS,
    MIN_HIGHLIGHT_ALPHA,
    Ink,
    parse_color,
    parse_number,
    parse_width,
)
from lectos.style import BOARD_STYLES, LASER_STYLES, MAX_LASER_PX, MIN_LASER_PX, LaserStyle

COLOR_NAMES = ", ".join(COLORS)
TOOL_FLAG_MESSAGES = {  # (off, on); translate with tr() when shown
    "mouse_draw": (noop("mouse drawing off"), noop("mouse drawing on")),
    "eraser": (noop("eraser off"), noop("eraser on")),
}


class Tools:
    """Changes the pen, the chalkboard background and the laser look, and says what happened."""

    def __init__(self, ink: Ink, deck: Deck, laser: LaserStyle) -> None:
        self.ink, self.deck, self.laser = ink, deck, laser

    def color(self, arg: str) -> str:
        """Pen colour."""
        color = parse_color(arg)
        if color is None:
            return tr("colour: {names} or #rrggbb").format(names=COLOR_NAMES)
        self.ink.tool.color = color
        self.ink.notify()
        return tr("pen colour {color}").format(color=color)

    def width(self, arg: str) -> str:
        """Pen width."""
        width = parse_width(arg)
        if width is None:
            return tr("width needs 1..{maximum}").format(maximum=MAX_PEN_WIDTH)
        self.ink.tool.width = width
        self.ink.notify()
        return tr("pen width {width}").format(width=int(width))

    def highlighter(self, on: bool) -> str:
        """Switch between pen and highlighter."""
        self.ink.tool.highlighter = on
        self.ink.notify()
        return tr("highlighter on") if on else tr("pen")

    def smoothing(self, arg: str) -> str:
        """Stroke smoothing level."""
        value = parse_number(arg, 0, MAX_SMOOTHING)
        if value is None or value != int(value):
            return tr("smooth needs 0..{maximum}").format(maximum=MAX_SMOOTHING)
        self.ink.tool.smoothing = int(value)
        self.ink.notify()
        return tr("smoothing {level}").format(level=int(value))

    def eraser_size(self, arg: str) -> str:
        """Eraser radius in layer units."""
        value = parse_number(arg, MIN_ERASER_RADIUS, MAX_ERASER_RADIUS)
        if value is None:
            return tr("eraser-size needs {low}..{high}").format(
                low=f"{MIN_ERASER_RADIUS:g}", high=f"{MAX_ERASER_RADIUS:g}"
            )
        self.ink.tool.eraser_radius = value
        self.ink.notify()
        return tr("eraser radius {value}").format(value=f"{value:g}")

    def highlight_alpha(self, arg: str) -> str:
        """Highlighter opacity."""
        value = parse_number(arg, MIN_HIGHLIGHT_ALPHA, MAX_HIGHLIGHT_ALPHA)
        if value is None:
            return tr("highlight-alpha needs {low}..{high}").format(low=MIN_HIGHLIGHT_ALPHA, high=MAX_HIGHLIGHT_ALPHA)
        self.ink.tool.highlight_alpha = value
        self.ink.notify()
        return tr("highlighter opacity {value}").format(value=f"{value:g}")

    def board_style(self, arg: str) -> str:
        """Chalkboard background."""
        if not self.deck.set_board_style(arg):
            return tr("board-style: {names}").format(names=", ".join(BOARD_STYLES))
        return tr("board background {name}").format(name=arg)

    def laser_color(self, arg: str) -> str:
        """Laser colour."""
        color = parse_color(arg)
        if color is None:
            return tr("colour: {names} or #rrggbb").format(names=COLOR_NAMES)
        self.laser.color = color
        self.deck.touch()
        return tr("laser colour {color}").format(color=color)

    def laser_size(self, arg: str) -> str:
        """Laser radius in pixels."""
        value = parse_number(arg, MIN_LASER_PX, MAX_LASER_PX)
        if value is None:
            return tr("laser-size needs {low}..{high}").format(low=f"{MIN_LASER_PX:g}", high=f"{MAX_LASER_PX:g}")
        self.laser.size = value
        self.deck.touch()
        return tr("laser size {value}").format(value=f"{value:g}")

    def laser_style(self, arg: str) -> str:
        """Laser shape."""
        if arg not in LASER_STYLES:
            return tr("laser-style: {names}").format(names=", ".join(LASER_STYLES))
        self.laser.style = arg
        self.deck.touch()
        return tr("laser shape {name}").format(name=arg)

    def clear_all(self) -> str:
        """Erase every stroke on every slide and the chalkboard."""
        removed = self.ink.clear_all()
        return (
            tr("erased {count} strokes (undo restores a layer)").format(count=removed)
            if removed
            else tr("nothing to erase")
        )

    def restore_all(self) -> str:
        """Bring back what the last clear-all erased."""
        layers = self.ink.restore_cleared()
        return tr("restored ink on {count} layers").format(count=layers) if layers else tr("nothing to restore")
