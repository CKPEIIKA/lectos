"""The toolbar of the drawing layout: pen colours, pen width and the drawing buttons."""

from __future__ import annotations

from typing import Protocol

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from lectos.gtk.widgets.css import SWATCH_CLASS
from lectos.i18n import noop, tr
from lectos.model.ink import COLORS, MAX_PEN_WIDTH

BUTTONS = ("highlighter", "eraser", "undo", "redo", "clear", "board", "laser")  # header item names
COLOR_TIPS = {
    "red": noop("red"), "yellow": noop("yellow"), "green": noop("green"),
    "blue": noop("blue"), "white": noop("white"), "black": noop("black"),
}  # fmt: skip
SELECTED = "selected"
WIDTH_SCALE_PX = 140


class DrawHost(Protocol):
    """What the bar needs from the console."""

    def execute(self, line: str) -> None:
        """Run a command line."""

    def item_button(self, name: str) -> Gtk.Button:
        """A header-style button for a header item."""

    def pen_color_name(self) -> str:
        """Name of the current pen colour, or ''."""

    def pen_width(self) -> float:
        """Current pen width."""


class DrawBar(Gtk.Box):
    """Colour swatches, a width slider and the drawing buttons; every control runs a console command."""

    def __init__(self, host: DrawHost) -> None:
        super().__init__(spacing=8, halign=Gtk.Align.CENTER, margin_top=6, margin_bottom=6)
        self.host = host
        self._syncing = False
        self.swatches: dict[str, Gtk.Button] = {}
        for name in COLORS:
            swatch = Gtk.Button(css_classes=[SWATCH_CLASS, f"{SWATCH_CLASS}-{name}"], tooltip_text=tr(COLOR_TIPS[name]))
            swatch.connect("clicked", lambda _b, n=name: self.host.execute(f"color {n}"))
            self.swatches[name] = swatch
            self.append(swatch)
        self.width = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, MAX_PEN_WIDTH, 1)
        self.width.set_size_request(WIDTH_SCALE_PX, -1)
        self.width.set_tooltip_text(tr("pen width"))
        self.width.connect("value-changed", self._width_changed)
        self.append(self.width)
        self.buttons = {name: host.item_button(name) for name in BUTTONS}
        for button in self.buttons.values():
            self.append(button)
        self.sync()

    def _width_changed(self, scale: Gtk.Scale) -> None:
        if not self._syncing:
            self.host.execute(f"width {round(scale.get_value())}")

    def sync(self) -> None:
        """Show the real pen: the swatch of its colour and its width."""
        self._syncing = True
        try:
            current = self.host.pen_color_name()
            for name, swatch in self.swatches.items():
                (swatch.add_css_class if name == current else swatch.remove_css_class)(SELECTED)
            self.width.set_value(self.host.pen_width())
        finally:
            self._syncing = False
