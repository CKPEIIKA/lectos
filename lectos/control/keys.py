"""Vim-style key interpreter: counts, ``gg``, ``G`` and single-key commands."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from lectos.i18n import tr

ACTIONS = {
    "l": "next", "h": "prev", "j": "scroll-down", "k": "scroll-up",
    ":": "command-line", "/": "search", "n": "hit-next", "N": "hit-prev",
    "f": "projector-fullscreen", "F": "fullscreen", "b": "blackout",
    "z": "freeze", "o": "overview", "t": "timer",
    "d": "draw", "e": "eraser", "s": "sketch", "E": "edit", "S": "settings",
    "u": "undo", "U": "redo", "B": "board", "p": "laser", "?": "help", "x": "zoom",
}  # fmt: skip
RESERVED = frozenset("gG")  # g and G are the goto prefix; digits are counts
PENDING = "pending"


def check_binding(key: str, line: str, known: Iterable[str]) -> str | None:
    """Why ``key`` cannot run ``line`` (empty line = unbind), or None when it can."""
    if len(key) != 1 or not key.isprintable() or key.isspace():
        return tr("a key is one printable character")
    if key.isdigit() or key in RESERVED:
        return tr("{key} is used for counts and gg/G").format(key=key)
    name = line.split(maxsplit=1)[0] if line.strip() else ""
    if name and name not in {*known, "command-line"}:
        return tr("unknown command: {name} (:help lists them)").format(name=name)
    return None


@dataclass(frozen=True)
class Action:
    """A named command with its repeat count (None when no count was typed)."""

    name: str
    count: int | None = None
    arg: str = ""  # arguments bound to the key itself, e.g. ``color red``

    @property
    def line(self) -> str:
        """The command line to run: bound arguments, else the typed count."""
        return f"{self.name} {self.arg or ('' if self.count is None else self.count)}".strip()


class Vim:
    """Feed typed characters; get an Action, or None when the key is not consumed."""

    def __init__(self, bindings: Mapping[str, str] | None = None) -> None:
        self.bindings = {key: line for key, line in {**ACTIONS, **(bindings or {})}.items() if line}  # "" frees a key
        self.changed: dict[str, str] = {}  # keys bound while running; remembered so a restart keeps them
        self._digits = ""
        self._g = False

    def bind(self, key: str, line: str) -> None:
        """Make ``key`` run the command line ``line``; an empty line frees the key."""
        if line.strip():
            self.bindings[key] = line.strip()
        else:
            self.bindings.pop(key, None)
        self.changed[key] = line.strip()

    def rebind(self, arg: str, known: Iterable[str]) -> str:
        """The ``bind KEY COMMAND [ARGS]`` command (``bind KEY`` frees the key); returns what to tell the user."""
        key, _, line = arg.partition(" ")
        if not key:
            return tr("bind KEY COMMAND: make a key run a command (bind KEY alone frees it)")
        problem = check_binding(key, line, known)
        if problem:
            return tr("bind: {problem}").format(problem=problem)
        self.bind(key, line)
        if line.strip():
            return tr("key {key} runs {line}").format(key=key, line=line.strip())
        return tr("key {key} is free").format(key=key)

    def unbind(self, arg: str, known: Iterable[str]) -> str:
        """The ``unbind KEY`` command."""
        words = arg.split()
        return self.rebind(words[0] if words else "", known)

    def restore(self, saved: object, known: Iterable[str]) -> None:
        """Re-apply the keys remembered from an earlier run; entries that no longer fit are skipped."""
        names = set(known)
        for key, line in saved.items() if isinstance(saved, dict) else ():
            if isinstance(key, str) and isinstance(line, str) and check_binding(key, line, names) is None:
                self.bind(key, line)

    def key_for(self, command: str) -> str:
        """The key bound to a command (without arguments), or an empty string."""
        return next((key for key, line in self.bindings.items() if line == command), "")

    def _take(self) -> int | None:
        count = int(self._digits) if self._digits else None
        self._digits, self._g = "", False
        return count

    def feed(self, char: str) -> Action | None:
        """Interpret one character. ``Action("pending")`` means consumed, nothing to do yet."""
        if char.isdigit() and (char != "0" or self._digits):
            self._digits += char
            return Action(PENDING)
        if char == "g":
            if self._g:
                return Action("goto", self._take() or 1)
            self._g = True
            return Action(PENDING)
        if char == "G":
            count = self._take()
            return Action("goto", count) if count else Action("last")
        line = self.bindings.get(char)
        if line is None:
            self._take()
            return None
        name, _, arg = line.partition(" ")
        return Action(name, self._take(), arg.strip())

    def reset(self) -> None:
        """Drop any partial count or prefix."""
        self._take()


def key_for(command: str) -> str:
    """The vim-style key bound to a command, or an empty string."""
    return next((key for key, name in ACTIONS.items() if name == command), "")
