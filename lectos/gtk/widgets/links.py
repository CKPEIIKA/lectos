"""Clicking PDF links on a slide preview: go to the page they name or open the address in the desktop's browser."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from lectos.draw.stage import Stage
from lectos.model.ink import Ink
from lectos.model.links import Link, hit, is_safe

LINK_CURSOR = "pointer"


def launch(uri: str) -> str:
    """Open a web or mail address with the desktop's default program; returns an error text or ''."""
    if not is_safe(uri):
        return f"{uri}: only http, https and mailto links are opened"
    try:
        Gio.AppInfo.launch_default_for_uri(uri, None)
    except GLib.Error as exc:
        return f"{uri}: {exc.message}"
    return ""


class LinkInput:
    """Attach to a DrawingArea showing ``get_page()``; a click on a link calls ``on_page`` or ``on_uri``.

    Links are inactive while the mouse draws, on the chalkboard, and for pen input (a pen stroke is not a click).
    """

    def __init__(
        self,
        area: Gtk.DrawingArea,
        stage: Stage,
        ink: Ink,
        get_page: Callable[[], int],
        *,
        on_page: Callable[[int], None],
        on_uri: Callable[[str], None],
    ) -> None:
        self.area, self.stage, self.ink, self.get_page = area, stage, ink, get_page
        self.on_page, self.on_uri = on_page, on_uri
        self._over = False
        click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
        click.connect("released", self._released)
        area.add_controller(click)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._moved)
        motion.connect("leave", lambda _c: self._show_pointer(False))
        area.add_controller(motion)

    def link_at(self, x: float, y: float) -> Link | None:
        """The link under a widget position, if links are active."""
        if self.stage.deck.board or self.ink.tool.mouse_draw:
            return None
        page = self.get_page()
        if not 0 <= page < self.stage.deck.pages:
            return None
        lx, ly = self.stage.to_layer(page, self.area.get_width(), self.area.get_height(), x, y)
        return hit(self.stage.doc.links(page), lx, ly)

    def _moved(self, _controller: Gtk.EventControllerMotion, x: float, y: float) -> None:
        self._show_pointer(self.link_at(x, y) is not None)

    def _show_pointer(self, over: bool) -> None:
        if over != self._over:
            self._over = over
            self.area.set_cursor_from_name(LINK_CURSOR if over else None)

    @staticmethod
    def _is_pen(gesture: Gtk.GestureClick) -> bool:
        device = gesture.get_current_event_device()
        return device is not None and device.get_source() in (Gdk.InputSource.PEN, Gdk.InputSource.TABLET_PAD)

    def _released(self, gesture: Gtk.GestureClick, _presses: int, x: float, y: float) -> None:
        if self._is_pen(gesture):
            return
        link = self.link_at(x, y)
        if link is None:
            return
        if link.page is not None:
            self.on_page(link.page)
        else:
            self.on_uri(link.uri)
