"""Console layout rules: compact for a notebook, wide for a big screen. No GUI code."""

from __future__ import annotations

COMPACT = "compact"
WIDE = "wide"
AUTO = "auto"
MODES = (AUTO, COMPACT, WIDE)
WIDE_ENTER_PX = 1500  # auto switches to wide at this window width ...
WIDE_LEAVE_PX = 1380  # ... and back to compact below this one, so resizing does not flicker
DEFAULT_PREVIOUS = 3
DEFAULT_UPCOMING = 8
MAX_PREVIOUS = 8
MAX_UPCOMING = 16
MIN_THUMB_PX = 96
MAX_THUMB_PX = 260
STRIP_GAP_PX = 6


def resolve(mode: str, width: int, current: str = COMPACT) -> str:
    """The layout to show for a mode and window width. ``current`` provides hysteresis in auto mode."""
    if mode in (COMPACT, WIDE):
        return mode
    if current == WIDE:
        return WIDE if width >= WIDE_LEAVE_PX else COMPACT
    return WIDE if width >= WIDE_ENTER_PX else COMPACT


def strip_pages(view: int, pages: int, previous: int, upcoming: int) -> list[int]:
    """Pages shown in the filmstrip: ``previous`` before the view, the view, ``upcoming`` after, clipped to the deck."""
    first = max(0, view - previous)
    last = min(pages - 1, view + upcoming)
    return list(range(first, last + 1))


def thumb_width(available: int, count: int) -> int:
    """Width of one filmstrip thumbnail so ``count`` of them fit in ``available`` pixels."""
    if count <= 0:
        return MAX_THUMB_PX
    fit = (available - STRIP_GAP_PX * (count + 1)) // count
    return max(MIN_THUMB_PX, min(MAX_THUMB_PX, fit))


def clamp_count(value: int, maximum: int) -> int:
    """Limit a previous/upcoming slide count to 0..maximum."""
    return max(0, min(value, maximum))
