from pathlib import Path

import pytest

from lectos import state


def test_state_roundtrip_is_atomic_and_private_to_pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "st"))
    pdf = tmp_path / "a.pdf"
    other = tmp_path / "b.pdf"
    assert state.load(pdf) == {}
    state.save(pdf, {"page": 3, "timer": {"running": False}})
    assert state.load(pdf) == {"page": 3, "timer": {"running": False}}
    assert state.load(other) == {}
    assert [p.name for p in state.state_path(pdf).parent.iterdir()] == [state.state_path(pdf).name]


def test_state_rejects_oversize(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    with pytest.raises(ValueError, match="too large"):
        state.save(tmp_path / "a.pdf", {"x": "y" * state.MAX_STATE_BYTES})


def test_ink_kind_is_a_separate_larger_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    pdf = tmp_path / "a.pdf"
    state.save(pdf, {"page": 1})
    big: dict[str, object] = {"layers": {"s0": "y" * (state.MAX_STATE_BYTES * 2)}}
    state.save(pdf, big, "ink")  # exceeds the state limit but not the ink limit
    assert state.load(pdf) == {"page": 1}
    assert state.load(pdf, "ink") == big
    assert state.state_path(pdf, "ink") != state.state_path(pdf)


def test_a_failed_write_leaves_no_temporary_file_and_keeps_the_old_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    pdf = tmp_path / "a.pdf"
    state.save(pdf, {"page": 1})

    def boom(*_args: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(state.os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        state.save(pdf, {"page": 2})
    monkeypatch.undo()
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert state.load(pdf) == {"page": 1}
    assert [p.name for p in state.state_path(pdf).parent.iterdir()] == [state.state_path(pdf).name]


def test_edited_notes_get_their_own_markdown_file_per_pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    one, two = tmp_path / "a.pdf", tmp_path / "b.pdf"
    assert state.edits_path(one).suffix == ".md"
    assert state.edits_path(one) != state.edits_path(two)
    assert state.edits_path(one).parent == state.state_path(one).parent


def test_the_last_chooser_folder_is_remembered_while_it_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    assert state.last_folder() is None
    folder = tmp_path / "lectures"
    folder.mkdir()
    state.remember_folder(folder)
    assert state.last_folder() == folder
    folder.rmdir()
    assert state.last_folder() is None


def test_remembering_a_folder_never_fails_the_caller(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    blocked = tmp_path / "state"
    blocked.write_text("a file where the folder should be")
    monkeypatch.setenv("XDG_STATE_HOME", str(blocked))
    state.remember_folder(tmp_path)
    assert state.last_folder() is None


def test_the_crash_log_is_armed_only_while_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import faulthandler

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    with state.crash_log():
        assert faulthandler.is_enabled()
    assert not faulthandler.is_enabled()
    assert (tmp_path / "state" / "lectos" / "crash.log").is_file()


def test_an_unwritable_state_folder_does_not_stop_the_crash_log_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocked = tmp_path / "state"
    blocked.write_text("a file where the folder should be")
    monkeypatch.setenv("XDG_STATE_HOME", str(blocked))
    with state.crash_log():
        pass
