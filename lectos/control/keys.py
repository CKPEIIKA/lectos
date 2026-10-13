"""Vim-style key interpreter: counts, ``gg``, ``G`` and single-key commands."""

from __future__ import annotations

from dataclasses import dataclass

ACTIONS = {
    "l": "next", "h": "prev", "j": "scroll-down", "k": "scroll-up",
    ":": "command-line", "/": "search", "n": "hit-next", "N": "hit-prev",
    "f": "projector-fullscreen", "F": "fullscreen", "b": "blackout",
    "z": "freeze", "o": "overview", "t": "timer",
    "d": "draw", "e": "eraser", "s": "sketch", "E": "edit", "S": "settings",
    "u": "undo", "U": "redo", "B": "board", "p": "laser", "?": "help",
}  # fmt: skip


@dataclass(frozen=True)
class Action:
    """A named command with its repeat count (None when no count was typed)."""

    name: str
    count: int | None = None


class Vim:
    """Feed typed characters; get an Action, or None when the key is not consumed."""

    def __init__(self) -> None:
        self._digits = ""
        self._g = False

    def _take(self) -> int | None:
        count = int(self._digits) if self._digits else None
        self._digits, self._g = "", False
        return count

    def feed(self, char: str) -> Action | None:
        """Interpret one character. ``Action("pending")`` means consumed, nothing to do yet."""
        if char.isdigit() and (char != "0" or self._digits):
            self._digits += char
            return Action("pending")
        if char == "g":
            if self._g:
                return Action("goto", self._take() or 1)
            self._g = True
            return Action("pending")
        if char == "G":
            count = self._take()
            return Action("goto", count) if count else Action("last")
        name = ACTIONS.get(char)
        if name is None:
            self._take()
            return None
        return Action(name, self._take())

    def reset(self) -> None:
        """Drop any partial count or prefix."""
        self._take()


def key_for(command: str) -> str:
    """The vim-style key bound to a command, or an empty string."""
    return next((key for key, name in ACTIONS.items() if name == command), "")
