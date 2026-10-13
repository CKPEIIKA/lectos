"""The ``:`` command line: parsing, flags, counts and Tab completion. No GUI code."""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass

from lectos.i18n import noop, tr

LAST_MARK = "$"


def parse(line: str) -> tuple[str, str]:
    """Split a command line into (name, argument). A bare number is ``goto N``, ``$`` is ``last``."""
    text = line.lstrip(":").strip()
    if text.isdigit():
        return "goto", text
    if text == LAST_MARK:
        return "last", ""
    name, _, arg = text.partition(" ")
    return name, arg.strip()


def count(arg: str) -> int:
    """Repeat count from an argument; 1 when absent or not a number."""
    return int(arg) if arg.isdigit() else 1


def flag(arg: str, current: bool) -> bool:
    """Interpret ``on``/``off``; an empty argument toggles ``current``."""
    return {"on": True, "off": False}.get(arg.lower(), not current)


def _common_prefix(words: list[str]) -> str:
    first, last = words[0], words[-1]  # sorted, so these two bound the shared prefix
    n = 0
    while n < min(len(first), len(last)) and first[n] == last[n]:
        n += 1
    return first[:n]


def complete(line: str, names: Iterable[str]) -> tuple[str, list[str]]:
    """Complete the command name in ``line`` from ``names``.

    Returns the new line and the candidates. A unique match is completed with a trailing
    space; several matches extend to their common prefix. Text after the first word is untouched.
    """
    text = line.lstrip(":")
    if " " in text:
        return line, []
    matches = sorted(n for n in names if n.startswith(text))
    if not matches:
        return line, []
    if len(matches) == 1:
        return f":{matches[0]} ", matches
    return ":" + _common_prefix(matches), matches


@dataclass(frozen=True)
class Help:
    """One command's usage line, a sentence about it, and the group it is listed under."""

    usage: str
    text: str
    group: str


GROUPS = (
    noop("Navigation"), noop("Notes"), noop("Timer"), noop("Projector"), noop("Drawing"), noop("Laser"),
    noop("View"), noop("General"),
)  # fmt: skip
HELP = {
    "next": Help("next [N]", noop("Next slide, or N slides forward."), noop("Navigation")),
    "prev": Help("prev [N]", noop("Previous slide, or N slides back."), noop("Navigation")),
    "goto": Help("goto N", noop("Go to slide N. A bare number does the same: :12"), noop("Navigation")),
    "first": Help("first", noop("Go to the first slide."), noop("Navigation")),
    "last": Help("last", noop("Go to the last slide. :$ does the same."), noop("Navigation")),
    "overview": Help("overview", noop("List or grid of all slides; pick one to go there."), noop("Navigation")),
    "main": Help("main", noop("Leave the overview, search or help and return to the main view."), noop("Navigation")),
    "search": Help("search [TEXT]", noop("Search slide text and notes. /TEXT does the same."), noop("Notes")),
    "hit-next": Help("hit-next", noop("Next search hit (key n)."), noop("Notes")),
    "hit-prev": Help("hit-prev", noop("Previous search hit (key N)."), noop("Notes")),
    "show-slide": Help(
        "show-slide [on|off]",
        noop("Whether a note hit also previews its slide (never moves the projector)."),
        noop("Notes"),
    ),
    "edit": Help(
        "edit",
        noop("Edit the notes of the viewed slide. Markdown notes are rewritten; a Beamer .tex is never changed."),
        noop("Notes"),
    ),
    "scroll-down": Help("scroll-down [N]", noop("Scroll the notes down."), noop("Notes")),
    "scroll-up": Help("scroll-up [N]", noop("Scroll the notes up."), noop("Notes")),
    "timer": Help("timer", noop("Start or pause the timer."), noop("Timer")),
    "timer-reset": Help("timer-reset", noop("Stop the timer and set it to zero."), noop("Timer")),
    "target": Help(
        "target LENGTH",
        noop("Planned lecture length, e.g. 90, 1h30, 1:30 or 45m; drives the time left."),
        noop("Timer"),
    ),
    "freeze": Help(
        "freeze [on|off]",
        noop("Hold the projector on its slide while you browse; unfreezing catches it up."),
        noop("Projector"),
    ),
    "blackout": Help(
        "blackout [on|off]",
        noop("Black out the projector (shows the standby screen if configured)."),
        noop("Projector"),
    ),
    "board": Help("board [on|off]", noop("Show the chalkboard instead of the slide."), noop("Projector")),
    "board-style": Help(
        "board-style NAME", noop("Chalkboard background: chalk, black, white, ruled, grid."), noop("Projector")
    ),
    "fullscreen": Help(
        "fullscreen [on|off]",
        noop("Fullscreen for the console window (GTK) or the projector (terminal)."),
        noop("Projector"),
    ),
    "projector-fullscreen": Help(
        "projector-fullscreen [on|off]", noop("Fullscreen for the projector window."), noop("Projector")
    ),
    "draw": Help("draw [on|off]", noop("Let the mouse draw (a pen always draws)."), noop("Drawing")),
    "eraser": Help("eraser [on|off]", noop("Erase whole strokes you touch instead of drawing."), noop("Drawing")),
    "highlighter": Help(
        "highlighter [on|off]", noop("Wide translucent strokes instead of pen strokes."), noop("Drawing")
    ),
    "color": Help("color NAME|#rrggbb", noop("Pen colour: red, yellow, green, blue, white, black."), noop("Drawing")),
    "width": Help("width N", noop("Pen width 1..40."), noop("Drawing")),
    "smooth": Help("smooth N", noop("Smooth finished strokes, 0 (off) to 5."), noop("Drawing")),
    "eraser-size": Help("eraser-size N", noop("Eraser radius, 4..80."), noop("Drawing")),
    "highlight-alpha": Help("highlight-alpha X", noop("Highlighter opacity, 0.1..0.9."), noop("Drawing")),
    "undo": Help("undo", noop("Undo the last ink change on this slide (or the board)."), noop("Drawing")),
    "redo": Help("redo", noop("Redo it."), noop("Drawing")),
    "clear": Help("clear", noop("Erase all ink on this slide (or the board); undo brings it back."), noop("Drawing")),
    "clear-all": Help(
        "clear-all",
        noop("Erase ALL ink on every slide and the board; undo restores a layer at a time."),
        noop("Drawing"),
    ),
    "restore-all": Help("restore-all", noop("Bring back the ink the last clear-all erased."), noop("Drawing")),
    "export": Help(
        "export [FILE]", noop("Write the slides with your ink to a new PDF (never overwrites)."), noop("Drawing")
    ),
    "export-ink": Help(
        "export-ink [FILE]",
        noop("Write this slide's (or the board's) drawing layer alone to a transparent PNG (never overwrites)."),
        noop("Drawing"),
    ),
    "laser": Help(
        "laser [on|off]", noop("Laser pointer: the dot follows the mouse over the large preview."), noop("Laser")
    ),
    "laser-color": Help("laser-color NAME|#rrggbb", noop("Laser colour."), noop("Laser")),
    "laser-size": Help("laser-size N", noop("Laser radius in pixels, 3..30."), noop("Laser")),
    "laser-style": Help("laser-style NAME", noop("Laser shape: dot, ring, cross."), noop("Laser")),
    "layout": Help(
        "layout auto|compact|wide|draw|toggle",
        noop("Console layout: notebook, big screen, quick drawing, or by window width."),
        noop("View"),
    ),
    "upcoming": Help(
        "upcoming N", noop("Slides shown after the current one in the wide layout's filmstrip, 0..16."), noop("View")
    ),
    "previous": Help("previous N", noop("Slides shown before the current one in the filmstrip, 0..8."), noop("View")),
    "sketch": Help(
        "sketch [on|off]", noop("Quick drawing layout: the slide large with a drawing toolbar (key s)."), noop("View")
    ),
    "panel": Help(
        "panel NAME [on|off]",
        noop("Show or hide a console part: notes, audience, next, strip (filmstrip) or status."),
        noop("View"),
    ),
    "settings": Help("settings", noop("Open the settings window."), noop("View")),
    "vim": Help("vim [on|off]", noop("Vim-style keys in the GTK console."), noop("View")),
    "open": Help("open", noop("Choose other slides, notes or a folder."), noop("General")),
    "help": Help("help [COMMAND]", noop("List every command with usage and keys, or describe one."), noop("General")),
    "quit": Help("quit", noop("Save and quit. q does the same."), noop("General")),
    "q": Help("q", noop("Same as quit."), noop("General")),
}


def help_entries(available: Collection[str], key_for: Callable[[str], str]) -> list[tuple[str, str, str, str]]:
    """(group, usage, text, key) for every available command, grouped in a fixed order then by name."""
    rows = [
        (GROUPS.index(HELP[name].group), name, HELP[name].group, HELP[name].usage, HELP[name].text, key_for(name))
        for name in available
        if name in HELP
    ]
    return [(group, usage, text, key) for _, _, group, usage, text, key in sorted(rows)]


def describe(name: str, key_for: Callable[[str], str]) -> str:
    """One line for ``help NAME``: usage, description and key."""
    entry = HELP.get(name)
    if entry is None:
        return tr("{name}: no such command (:help lists them)").format(name=name)
    key = key_for(name)
    return f"{entry.usage}: {tr(entry.text)}" + (f"  [{tr('key')} {key}]" if key else "")
