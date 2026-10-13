"""The projector contract shared by every console, plus the deck-to-projector sync. No GUI code."""

from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Protocol

from lectos.i18n import tr
from lectos.model.deck import Deck

GTK_CAPS = frozenset({"blackout", "board", "ink", "laser"})  # what our own window can show


class Projector(Protocol):
    """The audience window. ``caps`` lists optional features it supports (see ``GTK_CAPS``)."""

    caps: frozenset[str]

    def goto(self, page: int) -> None:
        """Show the zero-based page."""

    def fullscreen(self, on: bool) -> None:
        """Enter or leave fullscreen."""

    def is_fullscreen(self) -> bool:
        """Whether the window is fullscreen."""

    def stop(self) -> None:
        """Close the window."""


class NullProjector:
    """No audience window: the console is used on its own."""

    caps: frozenset[str] = frozenset()

    def goto(self, page: int) -> None:
        """Ignore."""

    def fullscreen(self, on: bool) -> None:
        """Ignore."""

    def is_fullscreen(self) -> bool:
        """Never fullscreen."""
        return False

    def stop(self) -> None:
        """Ignore."""


class ProjectorSync:
    """Keeps the projector on ``deck.page``. Errors are reported, never raised into the UI."""

    def __init__(self, deck: Deck, projector: Projector, report: Callable[[str], None]) -> None:
        self.deck, self.projector, self.report = deck, projector, report
        self._shown = -1
        deck.subscribe(self.sync)

    def sync(self) -> None:
        """Send the projected page if it changed since the last call."""
        if self.deck.page == self._shown:
            return
        self._shown = self.deck.page
        try:
            self.projector.goto(self.deck.page)
        except RuntimeError as exc:  # ProjectorError and friends
            self.report(tr("projector: {error}").format(error=exc))

    def force(self) -> None:
        """Send the projected page unconditionally (startup)."""
        self._shown = -1
        self.sync()


def gated(
    handler: Callable[[str], None], cap: str, caps: Collection[str], say: Callable[[str], None], name: str
) -> Callable[[str], None]:
    """Wrap a command that needs projector capability ``cap``; without it, say so instead of acting."""
    if cap in caps:
        return handler
    return lambda _arg: say(tr("{name}: not supported by this projector").format(name=name))


COMMAND_CAPS = {
    "blackout": "blackout", "board": "board", "laser": "laser",
    "clear": "ink", "undo": "ink", "redo": "ink", "draw": "ink", "eraser": "ink", "color": "ink", "width": "ink",
    "highlighter": "ink", "smooth": "ink", "eraser-size": "ink", "highlight-alpha": "ink", "clear-all": "ink",
    "restore-all": "ink", "board-style": "board", "laser-color": "laser", "laser-size": "laser", "laser-style": "laser",
}  # fmt: skip


def apply_caps(
    table: dict[str, Callable[[str], None]], caps: Collection[str], say: Callable[[str], None]
) -> dict[str, Callable[[str], None]]:
    """Gate every command in ``table`` that needs a projector capability the projector lacks."""
    for name, cap in COMMAND_CAPS.items():
        if name in table:
            table[name] = gated(table[name], cap, caps, say, name)
    return table
