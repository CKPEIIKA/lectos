"""Translations: gettext-style ``.po`` catalogs shipped as plain text and read at start-up. No GUI code.

Mark a string to show with ``tr("text")``; mark a string that is stored in a table and shown later with
``noop("text")`` and translate it with ``tr()`` where it is displayed. Both take a literal, so
``tests/test_i18n.py`` can check that every marked string has a translation.
"""

from __future__ import annotations

import os
import re
from importlib import resources

LANGUAGES = ("en", "ru", "de")
_catalog: dict[str, str] = {}
_STRING_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
_ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


def detect() -> str:
    """The language from the environment (LC_ALL, LC_MESSAGES, LANGUAGE, LANG), or English."""
    for name in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        value = os.environ.get(name, "")
        for part in value.split(":"):
            code = part.split(".")[0].split("_")[0].lower()
            if code in LANGUAGES:
                return code
    return "en"


def _unescape(text: str) -> str:
    return re.sub(r"\\(.)", lambda m: _ESCAPES.get(m.group(1), m.group(1)), text)


def _quoted(line: str) -> str | None:
    """The unescaped text of the first quoted string on a line."""
    match = _STRING_RE.search(line)
    return _unescape(match.group(1)) if match else None


def parse_po(text: str) -> dict[str, str]:
    """Read ``msgid``/``msgstr`` pairs (with continuation lines and comments); untranslated entries are skipped."""
    entries: dict[str, str] = {}
    current = {"id": "", "str": ""}
    field = "id"
    seen_id = False

    def flush() -> None:
        if seen_id and current["id"] and current["str"]:
            entries[current["id"]] = current["str"]

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("msgid "):
            flush()
            current, field, seen_id = {"id": _quoted(line) or "", "str": ""}, "id", True
        elif line.startswith("msgstr "):
            field = "str"
            current["str"] = _quoted(line) or ""
        elif line.startswith('"'):
            current[field] += _quoted(line) or ""
    flush()
    return entries


def load(language: str) -> dict[str, str]:
    """The catalog for a language; English (or an unknown language) has none."""
    if language not in LANGUAGES or language == "en":
        return {}
    path = resources.files("lectos").joinpath("locale", f"{language}.po")
    return parse_po(path.read_text(encoding="utf-8"))


def init(language: str = "auto") -> str:
    """Select the language ("auto" reads the environment) and load its catalog; returns the language in use."""
    chosen = detect() if language == "auto" else language
    chosen = chosen if chosen in LANGUAGES else "en"
    _catalog.clear()
    _catalog.update(load(chosen))
    return chosen


def tr(text: str) -> str:
    """The translation of ``text`` in the selected language, or ``text`` itself."""
    return _catalog.get(text, text)


def noop(text: str) -> str:
    """Mark ``text`` for translation without translating it yet (for strings kept in tables)."""
    return text
