"""Clickable areas of a slide (PDF links). No GUI code."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

SAFE_SCHEMES = ("http://", "https://", "mailto:")  # the only link targets lectos hands to the desktop


@dataclass(frozen=True)
class Link:
    """A rectangle in slide points (origin top-left) that goes to another page or opens an address."""

    x: float
    y: float
    width: float
    height: float
    page: int | None = None  # zero-based target page
    uri: str = ""

    def contains(self, x: float, y: float) -> bool:
        """Whether the point is inside the rectangle."""
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height


def hit(links: Sequence[Link], x: float, y: float) -> Link | None:
    """The link at a point; where several overlap, the one drawn last (on top)."""
    return next((link for link in reversed(links) if link.contains(x, y)), None)


def is_safe(uri: str) -> bool:
    """Whether lectos may open this address: web and mail links only, never local files or programs."""
    return uri.lower().startswith(SAFE_SCHEMES)
