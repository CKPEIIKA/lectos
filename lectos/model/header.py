"""Items that can appear in the console header bar: icon, fallback text, command. No GUI code."""

from __future__ import annotations

from dataclasses import dataclass

from lectos.i18n import noop


@dataclass(frozen=True)
class Item:
    """A header button. ``icons`` are symbolic icon names tried in order; ``label`` is used if the theme has none."""

    icons: tuple[str, ...]
    label: str
    command: str
    tip: str
    toggle: bool = False  # shows an on/off state kept in step with the deck, ink tool or projector


ITEMS = {
    "prev": Item(("go-previous-symbolic",), "◀", "prev", noop("previous slide (h)")),
    "next": Item(("go-next-symbolic",), "▶", "next", noop("next slide (l)")),
    "overview": Item(("view-grid-symbolic", "view-app-grid-symbolic"), "grid", "overview", noop("all slides (o)")),
    "search": Item(
        ("system-search-symbolic", "edit-find-symbolic"), "find", "search", noop("search slides and notes (/)")
    ),
    "freeze": Item(
        ("changes-prevent-symbolic", "system-lock-screen-symbolic"),
        "freeze",
        "freeze",
        noop("hold the projector (z)"),
        True,
    ),
    "blackout": Item(
        ("weather-clear-night-symbolic", "display-brightness-symbolic"),
        "black",
        "blackout",
        noop("black out the projector (b)"),
        True,
    ),
    "board": Item(("document-edit-symbolic",), "board", "board", noop("chalkboard (B)"), True),
    "laser": Item(
        ("find-location-symbolic", "media-record-symbolic"), "laser", "laser", noop("laser pointer (p)"), True
    ),
    "draw": Item(("tools-symbolic", "document-edit-symbolic"), "draw", "draw", noop("mouse drawing (d)"), True),
    "eraser": Item(("edit-clear-symbolic", "edit-delete-symbolic"), "eraser", "eraser", noop("eraser (e)"), True),
    "highlighter": Item(
        ("format-text-underline-symbolic", "tools-symbolic"), "mark", "highlighter", noop("highlighter"), True
    ),
    "clear": Item(("edit-clear-all-symbolic", "edit-clear-symbolic"), "clear", "clear", noop("clear slide ink")),
    "undo": Item(("edit-undo-symbolic",), "undo", "undo", noop("undo ink (u)")),
    "redo": Item(("edit-redo-symbolic",), "redo", "redo", noop("redo ink (U)")),
    "projector": Item(("video-display-symbolic",), "proj", "projector-fullscreen", noop("projector fullscreen (f)")),
    "fullscreen": Item(("view-fullscreen-symbolic",), "full", "fullscreen", noop("console fullscreen (F)")),
    "sketch": Item(
        ("applications-graphics-symbolic", "document-edit-symbolic"),
        "sketch",
        "sketch",
        noop("quick drawing layout (s)"),
        True,
    ),
    "layout": Item(("view-dual-symbolic",), "layout", "layout toggle", noop("switch compact / wide layout")),
}
SPECIAL = ("goto", "menu")  # widgets that are not plain buttons
ITEM_NAMES = (*ITEMS, *SPECIAL)
TITLES = ("timer", "slide", "none")
DEFAULT_START = ("prev", "next", "goto", "overview", "search")
DEFAULT_TITLE = "timer"
DEFAULT_END = ("layout", "sketch", "freeze", "blackout", "menu")  # displayed left to right
MAX_ITEMS = 14
