"""Pen and mouse input that draws or erases on a stage widget; used by both windows."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

from lectos.draw.stage import Stage
from lectos.model.ink import Ink

MOUSE_PRESSURE = 0.7
DRAW_CURSOR = "crosshair"
ERASE_CURSOR = "cell"


class InkInput:
    """Attach to a DrawingArea showing ``get_page()``; strokes go to that page's layer.

    A pen always draws (its eraser end erases); a mouse draws only when ``ink.tool.mouse_draw`` is on.
    The current tool decides between drawing and erasing.
    """

    def __init__(self, area: Gtk.DrawingArea, stage: Stage, ink: Ink, get_page: Callable[[], int]) -> None:
        self.area, self.stage, self.ink, self.get_page = area, stage, ink, get_page
        self._erasing = False
        self._drawing = False
        stylus = Gtk.GestureStylus()
        stylus.connect("down", self._stylus_down)
        stylus.connect("motion", self._stylus_motion)
        stylus.connect("up", self._up)
        area.add_controller(stylus)
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._mouse_begin)
        drag.connect("drag-update", self._mouse_update)
        drag.connect("drag-end", lambda *_: self._up())
        area.add_controller(drag)
        ink.subscribe(self.refresh_cursor)
        self.refresh_cursor()

    def refresh_cursor(self) -> None:
        """The pointer shows what the mouse will do: draw, erase, or (default cursor) nothing."""
        tool = self.ink.tool
        name = (ERASE_CURSOR if tool.eraser else DRAW_CURSOR) if tool.mouse_draw else None
        self.area.set_cursor_from_name(name)

    def _layer(self) -> str:
        return self.stage.layer(self.get_page())

    def _point(self, x: float, y: float) -> tuple[float, float]:
        return self.stage.to_layer(self.get_page(), self.area.get_width(), self.area.get_height(), x, y)

    def _begin(self, x: float, y: float, pressure: float, erase: bool) -> None:
        self._erasing = erase
        px, py = self._point(x, y)
        if erase:
            self.ink.erase_begin(self._layer())
            self.ink.erase_at(self._layer(), px, py)
        else:
            self.ink.begin(self._layer(), px, py, pressure)
            self._drawing = True

    def _move(self, x: float, y: float, pressure: float) -> None:
        px, py = self._point(x, y)
        if self._erasing:
            self.ink.erase_at(self._layer(), px, py)
        else:
            self.ink.extend(self._layer(), px, py, pressure)

    def _up(self, *_args: object) -> None:
        if self._erasing:
            self.ink.erase_end(self._layer())
            self._erasing = False
        elif self._drawing:
            self.ink.finish(self._layer())
            self._drawing = False

    def _stylus_down(self, gesture: Gtk.GestureStylus, x: float, y: float) -> None:
        tool = gesture.get_device_tool()
        eraser_end = tool is not None and tool.get_tool_type() == Gdk.DeviceToolType.ERASER
        ok, pressure = gesture.get_axis(Gdk.AxisUse.PRESSURE)
        self._begin(x, y, pressure if ok else 1.0, eraser_end or self.ink.tool.eraser)

    def _stylus_motion(self, gesture: Gtk.GestureStylus, x: float, y: float) -> None:
        ok, pressure = gesture.get_axis(Gdk.AxisUse.PRESSURE)
        self._move(x, y, pressure if ok else 1.0)

    @staticmethod
    def _is_pen(gesture: Gtk.GestureDrag) -> bool:
        """True when the current event comes from a pen; the stylus gesture handles those."""
        device = gesture.get_current_event_device()
        return device is not None and device.get_source() in (Gdk.InputSource.PEN, Gdk.InputSource.TABLET_PAD)

    def _mouse_begin(self, gesture: Gtk.GestureDrag, x: float, y: float) -> None:
        if not self._is_pen(gesture) and self.ink.tool.mouse_draw:
            self._begin(x, y, MOUSE_PRESSURE, self.ink.tool.eraser)

    def _mouse_update(self, gesture: Gtk.GestureDrag, dx: float, dy: float) -> None:
        if not self._is_pen(gesture) and self.ink.tool.mouse_draw:
            _, x, y = gesture.get_start_point()
            self._move(x + dx, y + dy, MOUSE_PRESSURE)
