"""Presentation model without any GUI code: projected page, private view, freeze, blackout, timer."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from lectos.i18n import tr
from lectos.model.style import BOARD_STYLES, DEFAULT_BOARD

SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60
DEFAULT_TARGET_MIN = 60
ON_TIME_S = 30  # within this of the plan counts as on time
MAX_TARGET_MIN = 24 * 60
_DURATION_RE = re.compile(r"(?:(?P<h>\d+)h)?(?:(?P<m>\d+)m?)?|(?P<hh>\d+):(?P<mm>\d{2})")


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def parse_minutes(text: str) -> int | None:
    """Parse a lecture length: ``90``, ``45m``, ``2h``, ``1h30``, ``1h30m`` or ``1:30`` into minutes (1 min to 24 h)."""
    compact = text.strip().lower().replace(" ", "")
    match = _DURATION_RE.fullmatch(compact)
    if not compact or match is None:
        return None
    if match.group("hh") is not None:
        hours, mins, bounded = int(match.group("hh")), int(match.group("mm")), True
    else:
        hours, mins = int(match.group("h") or 0), int(match.group("m") or 0)
        bounded = match.group("h") is not None  # "1h75" is ambiguous (write 2h15); a bare "75" is minutes
    if bounded and mins >= SECONDS_PER_MINUTE:
        return None
    minutes = hours * SECONDS_PER_MINUTE + mins
    return minutes if 1 <= minutes <= MAX_TARGET_MIN else None


def schedule_summary(timer: Timer, now: float, view: int, pages: int) -> str:
    """Footer text: ahead/behind the plan, estimated finish time, clock: ``ahead 2:10  ends 15:48  15:26``."""
    parts: list[str] = []
    delta = timer.schedule_delta(now, view, pages)
    if delta is not None:
        parts.append(
            tr("on time")
            if delta == 0
            else (tr("ahead {time}") if delta > 0 else tr("behind {time}")).format(time=format_seconds(abs(delta)))
        )
    parts.append(
        tr("ends {time}").format(time=time.strftime("%H:%M", time.localtime(timer.finish_at(now, view, pages))))
    )
    parts.append(time.strftime("%H:%M", time.localtime(now)))
    return "  ".join(parts)


def format_seconds(seconds: float) -> str:
    """Format as ``m:ss`` or ``h:mm:ss``, with a leading minus when negative."""
    total = round(abs(seconds))
    hours, rest = divmod(total, SECONDS_PER_HOUR)
    minutes, secs = divmod(rest, SECONDS_PER_MINUTE)
    sign = "-" if seconds < 0 else ""
    return f"{sign}{hours}:{minutes:02d}:{secs:02d}" if hours else f"{sign}{minutes}:{secs:02d}"


@dataclass
class Timer:
    """Stopwatch with a target length; the clock is passed in so it stays testable."""

    running: bool = False
    base: float = 0.0
    since: float = 0.0
    target_min: int = DEFAULT_TARGET_MIN

    def elapsed(self, now: float) -> float:
        """Seconds counted so far."""
        return self.base + (now - self.since if self.running else 0.0)

    def left(self, now: float) -> float:
        """Seconds until the target; negative when over."""
        return self.target_min * SECONDS_PER_MINUTE - self.elapsed(now)

    def pace_left(self, now: float, shown: int, total: int) -> float | None:
        """Estimated seconds for the remaining slides at the pace so far."""
        elapsed = self.elapsed(now)
        if shown < 1 or elapsed <= 0:
            return None
        return elapsed / shown * (total - shown)

    def schedule_delta(self, now: float, done: int, total: int) -> float | None:
        """Seconds ahead (positive) or behind (negative) the plan, or None before the timer has run.

        The plan gives every slide an equal share of the lecture length. Being on slide ``done`` (zero-based)
        for as long as its share is on time; arriving before its share started is ahead, staying past its end
        is behind.
        """
        elapsed = self.elapsed(now)
        if elapsed <= 0 or total <= 0:
            return None
        slot = self.target_min * SECONDS_PER_MINUTE / total
        start, end = slot * done, slot * (done + 1)
        if elapsed < start:
            return start - elapsed
        return end - elapsed if elapsed > end else 0.0

    def finish_at(self, now: float, done: int, total: int) -> float:
        """Epoch seconds when the lecture ends: at the current pace once it can be measured, else as planned."""
        remaining = self.pace_left(now, done + 1, total)
        return now + (self.left(now) if remaining is None else remaining)

    def toggle(self, now: float) -> None:
        """Start or pause."""
        if self.running:
            self.base = self.elapsed(now)
        else:
            self.since = now
        self.running = not self.running

    def reset(self) -> None:
        """Stop and zero the timer, keeping the target."""
        self.running, self.base = False, 0.0

    def to_dict(self) -> dict[str, object]:
        """Serializable form, including the start instant so a restart keeps counting."""
        return {"running": self.running, "base": self.base, "since": self.since, "target_min": self.target_min}

    def load(self, data: object) -> None:
        """Restore from ``to_dict`` output; malformed input leaves the timer unchanged."""
        if not isinstance(data, dict):
            return
        base, since, target = _number(data.get("base")), _number(data.get("since")), data.get("target_min")
        if base is None or since is None or not isinstance(target, int) or isinstance(target, bool) or target < 1:
            return
        self.base, self.since, self.target_min = base, since, target
        self.running = data.get("running") is True


class Deck:
    """Page state shared by the projector and the console."""

    def __init__(self, pages: int = 1) -> None:
        self.pages = pages
        self.page = 0  # what the audience sees
        self.view = 0  # what the presenter looks at
        self.frozen = False
        self.blackout = False
        self.board = False  # show the chalkboard instead of the slide
        self.board_style = DEFAULT_BOARD
        self.laser_on = False
        self.laser: tuple[float, float] | None = None  # fractions of the shown content
        self._subscribers: list[Callable[[], None]] = []

    def subscribe(self, callback: Callable[[], None]) -> None:
        """Call ``callback`` after every change."""
        self._subscribers.append(callback)

    def _changed(self) -> None:
        for callback in self._subscribers:
            callback()

    def clamp(self, page: int) -> int:
        """Limit a page to the document."""
        return max(0, min(page, self.pages - 1))

    def goto(self, page: int) -> None:
        """Move the view; the projector follows unless frozen."""
        self.view = self.clamp(page)
        if not self.frozen:
            self.page = self.view
        self._changed()

    def peek(self, page: int) -> None:
        """Move only the presenter's view, never the projector."""
        self.view = self.clamp(page)
        self._changed()

    def step(self, delta: int) -> None:
        """Move the view by ``delta`` pages."""
        self.goto(self.view + delta)

    def set_frozen(self, on: bool) -> None:
        """Hold the projector on its page; unfreezing catches it up to the view."""
        self.frozen = on
        if not on:
            self.page = self.view
        self._changed()

    def toggle_blackout(self) -> None:
        """Flip blackout."""
        self.blackout = not self.blackout
        self._changed()

    def touch(self) -> None:
        """Tell subscribers something visual changed (laser look, board style) without changing pages."""
        self._changed()

    def set_board_style(self, name: str) -> bool:
        """Choose the chalkboard background; False if the name is unknown."""
        if name not in BOARD_STYLES:
            return False
        self.board_style = name
        self._changed()
        return True

    def toggle_board(self) -> None:
        """Switch the audience between the slide and the chalkboard."""
        self.board = not self.board
        self._changed()

    def set_laser_on(self, on: bool) -> None:
        """Enable or disable the laser pointer; disabling hides the dot."""
        self.laser_on = on
        if not on:
            self.laser = None
        self._changed()

    def set_laser(self, position: tuple[float, float] | None) -> None:
        """Move the laser dot (None hides it). Ignored while the laser is off."""
        if self.laser_on or position is None:
            self.laser = position
            self._changed()

    def set_pages(self, pages: int) -> None:
        """Adopt a new page count (PDF recompiled), clamping both pages."""
        self.pages = max(1, pages)
        self.page, self.view = self.clamp(self.page), self.clamp(self.view)
        self._changed()

    def to_dict(self) -> dict[str, object]:
        """Serializable form."""
        return {
            "page": self.page, "view": self.view, "frozen": self.frozen, "board": self.board,
            "board_style": self.board_style,
        }  # fmt: skip

    def load(self, data: dict[str, object]) -> None:
        """Restore from ``to_dict`` output, ignoring malformed input."""
        page, view = data.get("page"), data.get("view")
        if isinstance(page, int) and not isinstance(page, bool):
            self.page = self.view = self.clamp(page)
        if data.get("frozen") is True and isinstance(view, int) and not isinstance(view, bool):
            self.frozen, self.view = True, self.clamp(view)
        self.board = data.get("board") is True
        style = data.get("board_style")
        if isinstance(style, str) and style in BOARD_STYLES:
            self.board_style = style
        self._changed()
