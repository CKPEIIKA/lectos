"""Ink strokes per layer with undo/redo and JSON persistence. No GUI code.

A layer is ``"board"`` or ``"s<page>"`` (zero-based page), so slide ink and chalkboard ink never mix.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field

MAX_UNDO = 50
MAX_PEN_WIDTH = 40
MAX_SMOOTHING = 5
MIN_ERASER_RADIUS = 4.0
MAX_ERASER_RADIUS = 80.0
HIGHLIGHT_WIDTH_FACTOR = 3.0
MIN_HIGHLIGHT_ALPHA = 0.1
MAX_HIGHLIGHT_ALPHA = 0.9
MAX_STROKES_PER_LAYER = 5000
MAX_POINTS_PER_STROKE = 20000
MIN_POINT_DISTANCE = 0.5
ERASER_RADIUS = 14.0
BOARD_LAYER = "board"
COLORS = {
    "red": "#e53935", "yellow": "#ffd90f", "green": "#43a047",
    "blue": "#1e88e5", "white": "#ffffff", "black": "#000000",
}  # fmt: skip
_SCHEMA_VERSION = 1
_HEX_RE = re.compile(r"#[0-9a-fA-F]{6}")

Point = tuple[float, float, float]


def slide_layer(page: int) -> str:
    """Layer key for a zero-based slide page."""
    return f"s{page}"


@dataclass
class Stroke:
    """A polyline in layer coordinates. Points are (x, y, pressure 0..1)."""

    points: list[Point] = field(default_factory=list)
    color: str = COLORS["yellow"]
    width: float = 4.0
    alpha: float = 1.0  # below 1 for highlighter strokes


@dataclass
class Tool:
    """Current pen settings. ``mouse_draw`` lets a mouse draw; a pen always does."""

    color: str = COLORS["yellow"]
    width: float = 4.0
    eraser: bool = False
    mouse_draw: bool = False
    highlighter: bool = False  # wide translucent strokes
    highlight_alpha: float = 0.35
    eraser_radius: float = ERASER_RADIUS
    smoothing: int = 0  # 0..MAX_SMOOTHING: how strongly a finished stroke is smoothed


def parse_color(arg: str) -> str | None:
    """A colour name from ``COLORS`` or ``#rrggbb``; None when invalid."""
    color = COLORS.get(arg.lower(), arg)
    return color if _HEX_RE.fullmatch(color) else None


def parse_width(arg: str) -> float | None:
    """A pen width 1..MAX_PEN_WIDTH; None when invalid."""
    return float(arg) if arg.isdigit() and 1 <= int(arg) <= MAX_PEN_WIDTH else None


def parse_number(arg: str, low: float, high: float) -> float | None:
    """A decimal number within [low, high]; None when invalid or out of range."""
    try:
        value = float(arg)
    except ValueError:
        return None
    return value if low <= value <= high else None


def smooth(points: list[Point], level: int) -> list[Point]:
    """Moving-average smoothing with window 2*level+1; the first and last point stay where they are."""
    if level <= 0 or len(points) < 4:  # noqa: PLR2004
        return points
    out: list[Point] = []
    last = len(points) - 1
    for i in range(len(points)):
        if i in (0, last):
            out.append(points[i])
            continue
        reach = min(level, i, last - i)
        window = points[i - reach : i + reach + 1]
        n = len(window)
        out.append((sum(p[0] for p in window) / n, sum(p[1] for p in window) / n, sum(p[2] for p in window) / n))
    return out


def _near(stroke: Stroke, x: float, y: float, radius: float) -> bool:
    return any(math.hypot(px - x, py - y) <= radius for px, py, _ in stroke.points)


class Ink:
    """All strokes, the current tool, and per-layer undo history."""

    def __init__(self) -> None:
        self.layers: dict[str, list[Stroke]] = {}
        self.tool = Tool()
        self.dirty = False
        self.last_cleared: list[str] = []  # layers emptied by the latest clear_all
        self._undo: dict[str, list[list[Stroke]]] = {}
        self._redo: dict[str, list[list[Stroke]]] = {}
        self._subscribers: list[Callable[[], None]] = []

    def subscribe(self, callback: Callable[[], None]) -> None:
        """Call ``callback`` after every change."""
        self._subscribers.append(callback)

    def changed(self) -> None:
        """Mark persistent state dirty and notify subscribers."""
        self.dirty = True
        for callback in self._subscribers:
            callback()

    def notify(self) -> None:
        """Notify subscribers of a non-persistent change such as a tool setting."""
        for callback in self._subscribers:
            callback()

    def strokes(self, layer: str) -> list[Stroke]:
        """Strokes of a layer, oldest first."""
        return self.layers.get(layer, [])

    def _forget_cleared(self, layer: str) -> None:
        """Any later change to a layer means "restore the erased ink" no longer applies to it."""
        if layer in self.last_cleared:
            self.last_cleared.remove(layer)

    def _snapshot(self, layer: str) -> None:
        self._forget_cleared(layer)
        history = self._undo.setdefault(layer, [])
        history.append(list(self.layers.get(layer, [])))
        del history[:-MAX_UNDO]
        self._redo[layer] = []

    def begin(self, layer: str, x: float, y: float, pressure: float) -> None:
        """Start a stroke with the current tool; refused when the layer is full."""
        if len(self.strokes(layer)) >= MAX_STROKES_PER_LAYER:
            return
        self._snapshot(layer)
        tool = self.tool
        width = tool.width * HIGHLIGHT_WIDTH_FACTOR if tool.highlighter else tool.width
        alpha = tool.highlight_alpha if tool.highlighter else 1.0
        self.layers.setdefault(layer, []).append(Stroke([(x, y, pressure)], tool.color, width, alpha))
        self.changed()

    def finish(self, layer: str) -> None:
        """End the newest stroke: smooth it according to the tool's smoothing level."""
        strokes = self.strokes(layer)
        if strokes and self.tool.smoothing:
            strokes[-1].points = smooth(strokes[-1].points, self.tool.smoothing)
            self.changed()

    def extend(self, layer: str, x: float, y: float, pressure: float) -> None:
        """Add a point to the newest stroke, dropping points that barely move."""
        strokes = self.strokes(layer)
        if not strokes or len(strokes[-1].points) >= MAX_POINTS_PER_STROKE:
            return
        lx, ly, _ = strokes[-1].points[-1]
        if math.hypot(x - lx, y - ly) >= MIN_POINT_DISTANCE:
            strokes[-1].points.append((x, y, pressure))
            self.changed()

    def erase_begin(self, layer: str) -> None:
        """Start an erase gesture (one undo step)."""
        self._snapshot(layer)

    def erase_at(self, layer: str, x: float, y: float, radius: float | None = None) -> None:
        """Remove strokes that have a point within ``radius`` (default: the tool's) of (x, y)."""
        radius = self.tool.eraser_radius if radius is None else radius
        kept = [s for s in self.strokes(layer) if not _near(s, x, y, radius)]
        if len(kept) != len(self.strokes(layer)):
            self.layers[layer] = kept
            self.changed()

    def erase_end(self, layer: str) -> None:
        """Finish an erase gesture; drop the undo step if nothing was erased."""
        history = self._undo.get(layer, [])
        if history and history[-1] == self.strokes(layer):
            history.pop()

    def clear(self, layer: str) -> None:
        """Remove all strokes of a layer (undoable)."""
        if self.strokes(layer):
            self._snapshot(layer)
            self.layers[layer] = []
            self.changed()

    def clear_all(self) -> int:
        """Remove every stroke on every layer (each layer's undo can bring its strokes back); returns the count."""
        removed = 0
        self.last_cleared = []
        for layer in [name for name, strokes in self.layers.items() if strokes]:
            removed += len(self.layers[layer])
            self._snapshot(layer)
            self.layers[layer] = []
            self.last_cleared.append(layer)
        if removed:
            self.changed()
        return removed

    def restore_cleared(self) -> int:
        """Undo the latest clear_all on every layer it emptied; returns how many layers came back."""
        layers, self.last_cleared = self.last_cleared, []
        for layer in layers:
            self.undo(layer)
        return len(layers)

    def undo(self, layer: str) -> None:
        """Restore the layer as it was before the last change."""
        self._forget_cleared(layer)
        history = self._undo.get(layer, [])
        if history:
            self._redo.setdefault(layer, []).append(list(self.strokes(layer)))
            self.layers[layer] = history.pop()
            self.changed()

    def redo(self, layer: str) -> None:
        """Re-apply the last undone change."""
        self._forget_cleared(layer)
        future = self._redo.get(layer, [])
        if future:
            self._undo.setdefault(layer, []).append(list(self.strokes(layer)))
            self.layers[layer] = future.pop()
            self.changed()

    def to_dict(self) -> dict[str, object]:
        """Serializable form with coordinates rounded to keep files small."""
        layers = {
            name: [
                {
                    "c": s.color,
                    "w": s.width,
                    "a": s.alpha,
                    "p": [[round(x, 1), round(y, 1), round(p, 2)] for x, y, p in s.points],
                }
                for s in strokes
            ]
            for name, strokes in self.layers.items()
            if strokes
        }
        return {"version": _SCHEMA_VERSION, "layers": layers}

    def load(self, data: object) -> None:
        """Replace all strokes from ``to_dict`` output; malformed parts are skipped."""
        self.layers.clear()
        self._undo.clear()
        self._redo.clear()
        self.last_cleared = []
        raw = data.get("layers") if isinstance(data, dict) else None
        for name, strokes in raw.items() if isinstance(raw, dict) else []:
            parsed = [s for s in (_parse_stroke(item) for item in strokes) if s] if isinstance(strokes, list) else []
            if parsed:
                self.layers[str(name)] = parsed[:MAX_STROKES_PER_LAYER]
        self.dirty = False
        self.notify()


def _num(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _parse_stroke(item: object) -> Stroke | None:
    if not isinstance(item, dict) or not isinstance(item.get("p"), list):
        return None
    width, color = _num(item.get("w")), item.get("c")
    points: list[Point] = []
    for raw in item["p"][:MAX_POINTS_PER_STROKE]:
        nums = [_num(v) for v in raw] if isinstance(raw, list) and len(raw) == 3 else []  # noqa: PLR2004
        if nums and all(v is not None for v in nums):
            points.append((nums[0], nums[1], nums[2]))  # ty: ignore[invalid-argument-type]
    if not points or width is None or not isinstance(color, str) or not _HEX_RE.fullmatch(color):
        return None
    alpha = _num(item.get("a"))
    return Stroke(points, color, width, 1.0 if alpha is None else max(0.0, min(alpha, 1.0)))
