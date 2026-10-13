from pathlib import Path

import pytest

from lectos import config
from lectos.config import ConfigError, Options

ROOT = Path(__file__).parent.parent / "examples"


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "options.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_default_file_gives_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config.load() == Options()
    assert Options().blackout.custom is False


def test_missing_explicit_file_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not a file"):
        config.load(tmp_path / "nope.toml")


def test_blackout_image_resolves_relative_to_config(tmp_path: Path) -> None:
    (tmp_path / "cat.png").write_bytes(b"x")
    opts = config.load(write(tmp_path, '[blackout]\nimage = "cat.png"\ntext = "Stand by"\nbackground = "#112233"\n'))
    assert opts.blackout.image == tmp_path / "cat.png"
    assert (opts.blackout.text, opts.blackout.background, opts.blackout.custom) == ("Stand by", "#112233", True)


def test_console_options(tmp_path: Path) -> None:
    opts = config.load(write(tmp_path, "[console]\nvim = false\ntarget_min = 45\n"))
    assert (opts.vim, opts.target_min) == (False, 45)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[blackout]\nimag = 'x'\n", "unknown option"),
        ("[blackuot]\n", "unknown section"),
        ("[blackout]\nbackground = 'red; x'\n", "#rrggbb"),
        ("[blackout]\nimage = 'missing.png'\n", "not a file"),
        ("[console]\ntarget_min = 0\n", "target_min"),
        ("[console]\nvim = 'yes'\n", "must be bool"),
        ("[console]\ntarget_min = true\n", "target_min"),
        ("[blackout\n", "options.toml"),
    ],
)
def test_invalid_options_name_the_problem(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        config.load(write(tmp_path, text))


def test_sample_options_are_valid() -> None:
    opts = config.load(ROOT / "options.toml")
    assert opts.blackout.image == ROOT / "standby.svg"
    assert opts.blackout.text.startswith("Please stand by")


def test_ui_section_selects_console_and_projector(tmp_path: Path) -> None:
    opts = config.load(write(tmp_path, '[ui]\nconsole = "tui"\nprojector = "zathura"\n'))
    assert (opts.console, opts.projector) == ("tui", "zathura")
    assert config.load(write(tmp_path, "")).console is None


@pytest.mark.parametrize("text", ['[ui]\nconsole = "qt"\n', '[ui]\nprojector = "none"\n', "[ui]\nfoo = 1\n"])
def test_invalid_ui_options(tmp_path: Path, text: str) -> None:
    with pytest.raises(ConfigError):
        config.load(write(tmp_path, text))


def test_header_and_layout_options(tmp_path: Path) -> None:
    opts = config.load(
        write(
            tmp_path,
            '[header]\nstart = ["prev", "next"]\ntitle = "slide"\nend = ["menu"]\n'
            '[console]\nlayout = "wide"\nprevious = 2\nupcoming = 12\n',
        )
    )
    assert (opts.header.start, opts.header.title, opts.header.end) == (("prev", "next"), "slide", ("menu",))
    assert (opts.layout, opts.previous, opts.upcoming) == ("wide", 2, 12)
    default = config.load(write(tmp_path, ""))
    assert default.header == config.Header()
    assert (default.layout, default.upcoming) == ("auto", 8)


@pytest.mark.parametrize(
    "text",
    [
        '[header]\nstart = ["nope"]\n',
        '[header]\nstart = ["prev", "prev"]\n',
        '[header]\nend = "menu"\n',
        '[header]\ntitle = "clock"\n',
        "[header]\nfoo = 1\n",
        '[console]\nlayout = "huge"\n',
        "[console]\nupcoming = 99\n",
        "[console]\nprevious = -1\n",
    ],
)
def test_invalid_header_and_layout_options(tmp_path: Path, text: str) -> None:
    with pytest.raises(ConfigError):
        config.load(write(tmp_path, text))


def test_drawing_and_laser_options(tmp_path: Path) -> None:
    opts = config.load(
        write(
            tmp_path,
            '[drawing]\ncolor = "red"\nwidth = 7\nhighlighter_alpha = 0.5\n'
            'eraser_radius = 20\nsmoothing = 2\nboard = "ruled"\n'
            '[laser]\ncolor = "#00ff00"\nsize = 12\nstyle = "ring"\nhalo = false\n',
        )
    )
    assert (opts.drawing.color, opts.drawing.width, opts.drawing.board) == ("#e53935", 7.0, "ruled")
    assert (opts.drawing.highlighter_alpha, opts.drawing.eraser_radius, opts.drawing.smoothing) == (0.5, 20.0, 2)
    assert (opts.laser.color, opts.laser.size, opts.laser.style, opts.laser.halo) == ("#00ff00", 12.0, "ring", False)
    default = config.load(write(tmp_path, ""))
    assert default.drawing == config.Drawing()
    assert default.laser == config.Laser()


@pytest.mark.parametrize(
    "text",
    [
        '[drawing]\ncolor = "mauve"\n',
        "[drawing]\nwidth = 0\n",
        "[drawing]\nwidth = 41\n",
        '[drawing]\nwidth = "wide"\n',
        "[drawing]\nhighlighter_alpha = 1\n",
        "[drawing]\neraser_radius = 1\n",
        "[drawing]\nsmoothing = 6\n",
        '[drawing]\nboard = "neon"\n',
        "[drawing]\nfoo = 1\n",
        '[laser]\nstyle = "star"\n',
        "[laser]\nsize = 99\n",
        "[laser]\nhalo = 1\n",
        '[laser]\ncolor = "#12"\n',
    ],
)
def test_invalid_drawing_and_laser_options(tmp_path: Path, text: str) -> None:
    with pytest.raises(ConfigError):
        config.load(write(tmp_path, text))


def test_target_accepts_lengths_and_rejects_nonsense(tmp_path: Path) -> None:
    assert config.load(write(tmp_path, '[console]\ntarget_min = "1h30"\n')).target_min == 90
    assert config.load(write(tmp_path, "[console]\ntarget_min = 1000\n")).target_min == 1000
    for text in ('[console]\ntarget_min = "soon"\n', "[console]\ntarget_min = 0\n", "[console]\ntarget_min = 2000\n"):
        with pytest.raises(ConfigError, match="target_min"):
            config.load(write(tmp_path, text))
