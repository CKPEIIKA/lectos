"""Application CSS shared by the console widgets, installed once per process."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

from lectos.model.ink import COLORS

TIMER_CLASS = "lectos-timer"
SWATCH_CLASS = "lectos-swatch"
SWATCH_SIZE_PX = 28
_installed = False


def stylesheet() -> str:
    """The CSS text. Colours come from the fixed ``COLORS`` table, so no user text reaches it."""
    swatches = "".join(f".{SWATCH_CLASS}-{name} {{ background: {color}; }}" for name, color in COLORS.items())
    return (
        f".{TIMER_CLASS} {{ padding: 4px 10px; min-height: 32px; }}"
        f".{TIMER_CLASS} label {{ line-height: 1.5; }}"
        f".{SWATCH_CLASS} {{ min-width: {SWATCH_SIZE_PX}px; min-height: {SWATCH_SIZE_PX}px; padding: 0;"
        " border-radius: 50%; border: 2px solid alpha(currentColor, 0.35); }"
        f".{SWATCH_CLASS}.selected {{ border-color: @accent_color; border-width: 3px; }}" + swatches
    )


def install() -> None:
    """Add the stylesheet to the default display (the first call only)."""
    global _installed
    if _installed:
        return
    provider = Gtk.CssProvider()
    provider.load_from_string(stylesheet())
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    _installed = True
