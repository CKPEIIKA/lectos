"""Drawing styles shared by rendering and configuration: board backgrounds and the laser pointer. No GUI code."""

from __future__ import annotations

from dataclasses import dataclass

RGB = tuple[float, float, float]


@dataclass(frozen=True)
class BoardStyle:
    """A chalkboard background: colour, and optional ruling lines every ``spacing`` board units."""

    bg: RGB
    line: RGB | None = None
    spacing: float = 0.0
    grid: bool = False  # vertical lines too, not only horizontal


BOARD_STYLES = {
    "chalk": BoardStyle((0.07, 0.13, 0.11)),
    "black": BoardStyle((0.02, 0.02, 0.02)),
    "white": BoardStyle((0.98, 0.98, 0.96)),
    "ruled": BoardStyle((0.97, 0.96, 0.90), (0.62, 0.72, 0.88), 56.0),
    "grid": BoardStyle((0.07, 0.13, 0.11), (0.20, 0.32, 0.28), 50.0, grid=True),
}
DEFAULT_BOARD = "chalk"
LASER_STYLES = ("dot", "ring", "cross")
MIN_LASER_PX = 3.0
MAX_LASER_PX = 30.0


@dataclass
class LaserStyle:
    """How the laser pointer looks; mutable so a console can change it while presenting."""

    color: str = "#ff1a1a"
    size: float = 9.0  # radius in screen pixels
    style: str = "dot"
    halo: bool = True
