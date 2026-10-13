"""Case-insensitive substring search across slide text and notes."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

MAX_HITS = 50
SNIPPET_RADIUS = 50
MAX_QUERY_CHARS = 200


@dataclass(frozen=True)
class Hit:
    """A match. ``index`` is the zero-based page for slides, the section index for notes.

    ``slide`` is the one-based slide a notes section is tied to, if any.
    """

    kind: str
    index: int
    slide: int | None
    snippet: str


def _matches(kind: str, index: int, slide: int | None, text: str, needle: str) -> list[Hit]:
    flat = re.sub(r"\s+", " ", text)  # phrases may span line breaks and padding
    hay = flat.lower()
    hits: list[Hit] = []
    pos = hay.find(needle)
    while pos != -1:
        lo = max(0, pos - SNIPPET_RADIUS)
        hits.append(Hit(kind, index, slide, flat[lo : pos + len(needle) + SNIPPET_RADIUS].strip()))
        pos = hay.find(needle, pos + len(needle))
    return hits


def find(query: str, slides: Sequence[str], notes: Sequence[tuple[int | None, str]]) -> list[Hit]:
    """Return up to ``MAX_HITS`` matches, notes first, in document order."""
    needle = " ".join(query.lower().split())[:MAX_QUERY_CHARS]
    if not needle:
        return []
    hits: list[Hit] = []
    for i, (slide, text) in enumerate(notes):
        hits += _matches("notes", i, slide, text, needle)
    for i, text in enumerate(slides):
        hits += _matches("slide", i, i + 1, text, needle)
    return hits[:MAX_HITS]
