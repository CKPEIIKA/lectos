import argparse
import sys
import types
from pathlib import Path
from typing import ClassVar

import pytest

from lectos import cli
from lectos.config import Options
from lectos.projectors.zathura import ProjectorError
from lectos.term.pdftools import PdfToolError


@pytest.fixture
def chosen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        cli, "_dispatch", lambda console, projector, args, options: calls.append((console, projector)) or 0
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "none"))
    (tmp_path / "s.pdf").write_bytes(b"%PDF-")
    return calls


def options_file(tmp_path: Path, text: str) -> str:
    path = tmp_path / "o.toml"
    path.write_text(text)
    return str(path)


def test_defaults_per_entry_point(chosen: list[tuple[str, str]], tmp_path: Path) -> None:
    pdf = str(tmp_path / "s.pdf")
    assert cli.main([pdf]) == 0
    assert cli.main_tui([pdf]) == 0
    assert chosen == [("gtk", "gtk"), ("tui", "zathura")]


def test_config_beats_entry_default_and_flags_beat_config(chosen: list[tuple[str, str]], tmp_path: Path) -> None:
    pdf = str(tmp_path / "s.pdf")
    config = options_file(tmp_path, '[ui]\nconsole = "tui"\nprojector = "gtk"\n')
    assert cli.main([pdf, "--config", config]) == 0
    assert cli.main_tui([pdf, "--config", config]) == 0
    assert cli.main([pdf, "--config", config, "--console", "gtk", "--projector", "zathura"]) == 0
    assert chosen == [("tui", "gtk"), ("tui", "gtk"), ("gtk", "zathura")]


def test_bad_inputs_are_reported(
    chosen: list[tuple[str, str]], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main([str(tmp_path / "missing.pdf")]) == 2
    bad = options_file(tmp_path, '[ui]\nconsole = "qt"\n')
    assert cli.main([str(tmp_path / "s.pdf"), "--config", bad]) == 2
    assert "console must be one of" in capsys.readouterr().err
    assert chosen == []


def test_missing_gtk_is_explained(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(*_args: object) -> int:
        raise ImportError("No module named 'gi'")

    monkeypatch.setattr(cli, "_dispatch", boom)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "none"))
    (tmp_path / "s.pdf").write_bytes(b"%PDF-")
    assert cli.main([str(tmp_path / "s.pdf")]) == 1
    assert "GTK 4 with PyGObject" in capsys.readouterr().err


def test_terminal_console_path_never_imports_gtk_or_cairo() -> None:
    import subprocess
    import sys

    code = (
        "import sys\n"
        "class Block:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name.split('.')[0] in ('gi', 'cairo'):\n"
        "            raise ImportError(name)\n"
        "sys.meta_path.insert(0, Block())\n"
        "import lectos.cli, lectos.term.tui, lectos.term.pdftools\n"
        "import lectos.projectors.zathura, lectos.projectors.projection\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_parser_defaults() -> None:
    args = cli.build_parser("lectos").parse_args(["slides.pdf"])
    assert args.notes is None
    assert args.windowed is False


def test_running_the_package_as_a_module_prints_the_version(capsys: pytest.CaptureFixture[str]) -> None:
    import runpy
    import sys

    argv = sys.argv
    sys.argv = ["lectos", "--version"]
    try:
        with pytest.raises(SystemExit) as stop:
            runpy.run_module("lectos", run_name="__main__")
    finally:
        sys.argv = argv
    assert stop.value.code == 0
    assert capsys.readouterr().out.strip().startswith("0.")


# ---- flags and dispatch routes ----


def parse(*extra: str) -> argparse.Namespace:
    return cli.build_parser("lectos").parse_args(["slides.pdf", *extra])


def test_flags_reach_the_options(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: list[Options] = []
    monkeypatch.setattr(cli, "_dispatch", lambda console, projector, args, options: seen.append(options) or 0)
    (tmp_path / "s.pdf").write_bytes(b"%PDF-")
    assert cli.main([str(tmp_path / "s.pdf"), "--no-vim", "--layout", "wide", "--lang", "de"]) == 0
    assert (seen[0].vim, seen[0].layout) == (False, "wide")
    from lectos import i18n

    assert i18n.tr("Overview") == "Übersicht"
    i18n.init("en")


class Tty:
    @staticmethod
    def isatty() -> bool:
        return True


class FakeSys:
    """What ``cli`` sees as ``sys`` when run from a terminal; stderr stays the real, captured one."""

    stdin = Tty()
    stdout = Tty()

    @property
    def stderr(self) -> object:
        return sys.stderr


@pytest.fixture
def tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "sys", FakeSys())


def fake_module(monkeypatch: pytest.MonkeyPatch, name: str, **attrs: object) -> None:
    monkeypatch.setitem(sys.modules, name, types.SimpleNamespace(**attrs))


def test_the_gtk_console_route(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, ...]] = []
    fake_module(monkeypatch, "lectos.gtk.app", run=lambda *a, **k: calls.append((a, k)) or 41)
    assert cli._dispatch("gtk", "zathura", parse("--windowed", "--monitor", "1"), Options()) == 41
    _args, kwargs = calls[0]
    assert kwargs == {"projector": "zathura", "windowed": True, "monitor": 1}


def test_the_terminal_console_needs_a_terminal(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli._dispatch("tui", "zathura", parse(), Options()) == 2  # pytest's stdin is not a tty
    assert "interactive terminal" in capsys.readouterr().err


def test_the_terminal_console_with_our_gtk_projector(monkeypatch: pytest.MonkeyPatch, tty: None) -> None:
    calls: list[dict[str, object]] = []
    fake_module(monkeypatch, "lectos.gtk.tuiglib", run=lambda *a, **k: calls.append(k) or 7)
    assert cli._dispatch("tui", "gtk", parse("--fullscreen"), Options()) == 7
    assert calls[0]["fullscreen"] is True


class FakeZathura:
    instances: ClassVar[list["FakeZathura"]] = []
    fail_start = False

    def __init__(self, pdf: Path) -> None:
        self.pdf, self.events = pdf, []
        FakeZathura.instances.append(self)

    def start(self) -> None:
        self.events.append("start")
        if FakeZathura.fail_start:
            raise ProjectorError("no window")

    def stop(self) -> None:
        self.events.append("stop")


class FakeTui:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def execute(self, line: str) -> None:
        self.commands.append(line)


class Route:
    """Records what the terminal route did; ``make_error`` makes building the console fail."""

    def __init__(self) -> None:
        self.tui = FakeTui()
        self.ran = 0
        self.make_error: Exception | None = None


@pytest.fixture
def terminal_route(monkeypatch: pytest.MonkeyPatch, tty: None) -> Route:
    from lectos.projectors import zathura
    from lectos.term import tui as tui_module

    route = Route()
    FakeZathura.instances, FakeZathura.fail_start = [], False

    def make_tui(*_a: object, **_k: object) -> FakeTui:
        if route.make_error is not None:
            raise route.make_error
        return route.tui

    def run_select(*_a: object) -> None:
        route.ran += 1

    monkeypatch.setattr(zathura, "Zathura", FakeZathura)
    monkeypatch.setattr(tui_module, "make_tui", make_tui)
    monkeypatch.setattr(tui_module, "run_select", run_select)
    return route


def test_terminal_console_with_zathura_runs_and_always_closes_it(terminal_route: Route) -> None:
    assert cli._dispatch("tui", "zathura", parse("--fullscreen"), Options()) == 0
    assert terminal_route.ran == 1
    assert terminal_route.tui.commands == ["fullscreen on"]
    assert FakeZathura.instances[0].events == ["start", "stop"]


def test_terminal_console_without_a_projector_never_starts_zathura(terminal_route: Route) -> None:
    assert cli._dispatch("tui", "none", parse(), Options()) == 0
    assert FakeZathura.instances == []
    assert terminal_route.tui.commands == []


def test_a_projector_that_will_not_start_is_an_error_exit(
    terminal_route: Route, capsys: pytest.CaptureFixture[str]
) -> None:
    FakeZathura.fail_start = True
    assert cli._dispatch("tui", "zathura", parse(), Options()) == 1
    assert "no window" in capsys.readouterr().err
    assert terminal_route.ran == 0
    assert FakeZathura.instances[0].events == ["start", "stop"]


def test_a_poppler_failure_while_building_the_console_is_an_error_exit(
    terminal_route: Route, capsys: pytest.CaptureFixture[str]
) -> None:
    terminal_route.make_error = PdfToolError("pdfinfo failed")
    assert cli._dispatch("tui", "zathura", parse(), Options()) == 1
    assert "pdfinfo failed" in capsys.readouterr().err
    assert FakeZathura.instances[0].events == ["start", "stop"]


# ---- starting with a folder, with notes next to the slides, or with nothing ----
def test_slides_and_notes_are_found_in_a_folder(chosen: list[tuple[str, str]], tmp_path: Path, monkeypatch) -> None:
    seen = []
    monkeypatch.setattr(cli, "_dispatch", lambda console, projector, args, options: seen.append(args) or 0)
    (tmp_path / "talk.pdf").write_bytes(b"%PDF-")
    (tmp_path / "talk.md").write_text("notes")
    assert cli.main([str(tmp_path)]) == 0
    assert (seen[0].pdf, seen[0].notes) == (tmp_path / "talk.pdf", tmp_path / "talk.md")
    assert cli.main([str(tmp_path), str(tmp_path / "other.md")]) == 2  # an explicit notes file must exist


def test_notes_next_to_the_slides_are_used_without_being_named(monkeypatch, tmp_path: Path) -> None:
    seen = []
    monkeypatch.setattr(cli, "_dispatch", lambda console, projector, args, options: seen.append(args) or 0)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "none"))
    (tmp_path / "talk.pdf").write_bytes(b"%PDF-")
    (tmp_path / "talk.tex").write_text("x")
    assert cli.main([str(tmp_path / "talk.pdf")]) == 0
    assert seen[0].notes == tmp_path / "talk.tex"


def test_a_folder_without_a_pdf_is_an_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([str(tmp_path)]) == 2
    assert "no PDF in" in capsys.readouterr().err


def test_without_arguments_the_gtk_console_asks_for_slides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "none"))
    fake_module(monkeypatch, "lectos.gtk.app", run=lambda *a, **k: calls.append(a) or 0)
    assert cli.main([]) == 0
    assert calls[0][:2] == (None, None)


def test_the_terminal_console_cannot_start_without_slides(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "none"))
    assert cli.main_tui([]) == 2
    assert "needs the slides" in capsys.readouterr().err


def test_the_notes_pages_flag_reaches_the_options(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: list[Options] = []
    monkeypatch.setattr(cli, "_dispatch", lambda console, projector, args, options: seen.append(options) or 0)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "none"))
    (tmp_path / "s.pdf").write_bytes(b"%PDF-")
    assert cli.main([str(tmp_path / "s.pdf"), "--notes-pages", "left"]) == 0
    assert seen[0].notes_pages == "left"
