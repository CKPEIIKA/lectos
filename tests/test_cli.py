from pathlib import Path

import pytest

from lectos import cli


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
        "import lectos.cli, lectos.tui, lectos.zathura, lectos.pdftools, lectos.projection\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
