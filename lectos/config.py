"""User options from ``options.toml``: blackout screen and a few defaults. No GUI code."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from lectos import header as header_items
from lectos import i18n, style
from lectos import layout as layouts
from lectos.deck import MAX_TARGET_MIN, parse_minutes
from lectos.ink import (
    MAX_ERASER_RADIUS,
    MAX_HIGHLIGHT_ALPHA,
    MAX_SMOOTHING,
    MIN_ERASER_RADIUS,
    MIN_HIGHLIGHT_ALPHA,
    parse_color,
    parse_number,
    parse_width,
)

MAX_IMAGE_BYTES = 50 * 1024 * 1024
CONSOLES = ("gtk", "tui")
PROJECTORS = ("gtk", "zathura")
_COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}")


class ConfigError(ValueError):
    """Raised for an unreadable or invalid options file; the message names the offending key."""


@dataclass(frozen=True)
class Blackout:
    """What the projector shows on blackout: plain black unless an image or text is configured."""

    image: Path | None = None
    text: str = ""
    background: str = "#000000"
    text_color: str = "#ffffff"

    @property
    def custom(self) -> bool:
        """True when there is something to show besides black."""
        return self.image is not None or bool(self.text)


@dataclass(frozen=True)
class Header:
    """What the console header bar shows: items on the left, a title in the middle, items on the right."""

    start: tuple[str, ...] = header_items.DEFAULT_START
    title: str = header_items.DEFAULT_TITLE
    end: tuple[str, ...] = header_items.DEFAULT_END


@dataclass(frozen=True)
class Drawing:
    """Pen defaults and the chalkboard background."""

    color: str = "#ffd90f"
    width: float = 4.0
    highlighter_alpha: float = 0.35
    eraser_radius: float = 14.0
    smoothing: int = 0
    board: str = style.DEFAULT_BOARD


@dataclass(frozen=True)
class Laser:
    """Laser pointer look."""

    color: str = "#ff1a1a"
    size: float = 9.0
    style: str = "dot"
    halo: bool = True


@dataclass(frozen=True)
class Options:
    """All user options with their defaults."""

    blackout: Blackout = Blackout()
    vim: bool = True
    target_min: int = 60
    header: Header = Header()
    drawing: Drawing = Drawing()
    laser: Laser = Laser()
    layout: str = layouts.AUTO
    previous: int = layouts.DEFAULT_PREVIOUS
    upcoming: int = layouts.DEFAULT_UPCOMING
    language: str = "auto"  # "auto" reads the environment, or "en" / "ru"
    console: str | None = None  # "gtk" or "tui"; None means the entry point decides
    projector: str | None = None  # "gtk" or "zathura"; None means the entry point decides


def default_path() -> Path:
    """Location of the options file when ``--config`` is not given."""
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "lectos" / "options.toml"


def _section(data: dict[str, object], name: str, allowed: set[str]) -> dict[str, object]:
    section = data.get(name, {})
    if not isinstance(section, dict):
        raise ConfigError(f"[{name}] must be a table")
    unknown = sorted(set(section) - allowed)
    if unknown:
        raise ConfigError(f"unknown option [{name}] {', '.join(unknown)}")
    return section


def _typed[T](section: dict[str, object], key: str, kind: type[T], default: T, where: str) -> T:
    value = section.get(key, default)
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise ConfigError(f"{where}{key} must be {kind.__name__}")
    return value


def _color(section: dict[str, object], key: str, default: str, where: str) -> str:
    value = _typed(section, key, str, default, where)
    if not _COLOR_RE.fullmatch(value):
        raise ConfigError(f"{where}{key} must look like #rrggbb")
    return value


def _target(section: dict[str, object]) -> int:
    raw = section.get("target_min", Options.target_min)
    minutes = parse_minutes(raw) if isinstance(raw, str) else raw
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= MAX_TARGET_MIN:
        raise ConfigError(f"[console] target_min must be minutes 1..{MAX_TARGET_MIN} or a length like 90, 1h30, 1:30")
    return minutes


def _items(section: dict[str, object], key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = section.get(key, list(default))
    if not isinstance(raw, list) or not all(isinstance(i, str) for i in raw):
        raise ConfigError(f"[header] {key} must be a list of names")
    bad = sorted(set(raw) - set(header_items.ITEM_NAMES))
    if bad:
        raise ConfigError(f"[header] {key}: unknown item {bad[0]!r} (known: {', '.join(header_items.ITEM_NAMES)})")
    if len(set(raw)) != len(raw) or len(raw) > header_items.MAX_ITEMS:
        raise ConfigError(f"[header] {key}: duplicates or more than {header_items.MAX_ITEMS} items")
    return tuple(raw)


def _count(section: dict[str, object], key: str, default: int, maximum: int) -> int:
    value = _typed(section, key, int, default, "[console] ")
    if not 0 <= value <= maximum:
        raise ConfigError(f"[console] {key} must be 0..{maximum}")
    return value


def _choice(section: dict[str, object], key: str, allowed: tuple[str, ...]) -> str | None:
    value = section.get(key)
    if value is None:
        return None
    if value not in allowed:
        raise ConfigError(f"[ui] {key} must be one of {', '.join(allowed)}")
    return str(value)


def _image(section: dict[str, object], base: Path) -> Path | None:
    raw = _typed(section, "image", str, "", "[blackout] ")
    if not raw:
        return None
    path = Path(raw).expanduser()
    path = path if path.is_absolute() else base / path
    if not path.is_file():
        raise ConfigError(f"[blackout] image: not a file: {path}")
    if path.stat().st_size > MAX_IMAGE_BYTES:
        raise ConfigError(f"[blackout] image: {path} exceeds {MAX_IMAGE_BYTES} bytes")
    return path


def _color_option(section: dict[str, object], key: str, default: str, where: str) -> str:
    raw = _typed(section, key, str, default, where)
    color = parse_color(raw)
    if color is None:
        raise ConfigError(f"{where}{key} must be a colour name or #rrggbb")
    return color


def _number_option(
    section: dict[str, object], key: str, default: float, bounds: tuple[float, float], where: str
) -> float:
    low, high = bounds
    raw = section.get(key, default)
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise ConfigError(f"{where}{key} must be a number")
    value = parse_number(str(raw), low, high)
    if value is None:
        raise ConfigError(f"{where}{key} must be {low:g}..{high:g}")
    return value


def _drawing(section: dict[str, object]) -> Drawing:
    where = "[drawing] "
    base = Drawing()
    width = _number_option(section, "width", base.width, (1, 40), where)
    if parse_width(str(int(width))) is None:
        raise ConfigError(f"{where}width must be 1..40")
    board = _typed(section, "board", str, base.board, where)
    if board not in style.BOARD_STYLES:
        raise ConfigError(f"{where}board must be one of {', '.join(style.BOARD_STYLES)}")
    return Drawing(
        color=_color_option(section, "color", base.color, where),
        width=width,
        highlighter_alpha=_number_option(
            section, "highlighter_alpha", base.highlighter_alpha, (MIN_HIGHLIGHT_ALPHA, MAX_HIGHLIGHT_ALPHA), where
        ),
        eraser_radius=_number_option(
            section, "eraser_radius", base.eraser_radius, (MIN_ERASER_RADIUS, MAX_ERASER_RADIUS), where
        ),
        smoothing=int(_number_option(section, "smoothing", base.smoothing, (0, MAX_SMOOTHING), where)),
        board=board,
    )


def _laser(section: dict[str, object]) -> Laser:
    where = "[laser] "
    base = Laser()
    look = _typed(section, "style", str, base.style, where)
    if look not in style.LASER_STYLES:
        raise ConfigError(f"{where}style must be one of {', '.join(style.LASER_STYLES)}")
    return Laser(
        color=_color_option(section, "color", base.color, where),
        size=_number_option(section, "size", base.size, (style.MIN_LASER_PX, style.MAX_LASER_PX), where),
        style=look,
        halo=_typed(section, "halo", bool, base.halo, where),
    )


def _header(section: dict[str, object]) -> Header:
    title = _typed(section, "title", str, header_items.DEFAULT_TITLE, "[header] ")
    if title not in header_items.TITLES:
        raise ConfigError(f"[header] title must be one of {', '.join(header_items.TITLES)}")
    return Header(
        _items(section, "start", header_items.DEFAULT_START), title, _items(section, "end", header_items.DEFAULT_END)
    )


def _layout_mode(section: dict[str, object]) -> str:
    mode = _typed(section, "layout", str, layouts.AUTO, "[console] ")
    if mode not in layouts.MODES:
        raise ConfigError(f"[console] layout must be one of {', '.join(layouts.MODES)}")
    return mode


def parse(data: dict[str, object], base: Path) -> Options:
    """Validate parsed TOML; relative image paths resolve against ``base``."""
    unknown = sorted(set(data) - {"blackout", "console", "ui", "header", "drawing", "laser"})
    if unknown:
        raise ConfigError(f"unknown section [{unknown[0]}]")
    black = _section(data, "blackout", {"image", "text", "background", "text_color"})
    console = _section(data, "console", {"vim", "target_min", "layout", "previous", "upcoming"})
    head = _section(data, "header", {"start", "title", "end"})
    draw = _section(data, "drawing", {"color", "width", "highlighter_alpha", "eraser_radius", "smoothing", "board"})
    pointer = _section(data, "laser", {"color", "size", "style", "halo"})
    ui = _section(data, "ui", {"console", "projector", "language"})
    target = _target(console)
    return Options(
        blackout=Blackout(
            image=_image(black, base),
            text=_typed(black, "text", str, "", "[blackout] "),
            background=_color(black, "background", Blackout.background, "[blackout] "),
            text_color=_color(black, "text_color", Blackout.text_color, "[blackout] "),
        ),
        vim=_typed(console, "vim", bool, Options.vim, "[console] "),
        target_min=target,
        header=_header(head),
        drawing=_drawing(draw),
        laser=_laser(pointer),
        layout=_layout_mode(console),
        previous=_count(console, "previous", layouts.DEFAULT_PREVIOUS, layouts.MAX_PREVIOUS),
        upcoming=_count(console, "upcoming", layouts.DEFAULT_UPCOMING, layouts.MAX_UPCOMING),
        language=_choice(ui, "language", ("auto", *i18n.LANGUAGES)) or "auto",
        console=_choice(ui, "console", CONSOLES),
        projector=_choice(ui, "projector", PROJECTORS),
    )


def load(path: Path | None = None) -> Options:
    """Load options. An explicit ``path`` must exist; the default location may be absent."""
    target = path or default_path()
    if not target.is_file():
        if path is not None:
            raise ConfigError(f"not a file: {path}")
        return Options()
    try:
        data = tomllib.loads(target.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"{target}: {exc}") from exc
    try:
        return parse(data, target.parent)
    except ConfigError as exc:
        raise ConfigError(f"{target}: {exc}") from exc
