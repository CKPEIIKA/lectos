import subprocess
from pathlib import Path

import pytest

from lectos.projectors import zathura
from lectos.projectors.zathura import ProjectorError, Zathura


class FakeProc:
    def __init__(self, *, alive: bool = True, stubborn: bool = False) -> None:
        self.pid = 4242
        self.alive = alive
        self.stubborn = stubborn
        self.events: list[str] = []

    def poll(self) -> int | None:
        return None if self.alive else 0

    def terminate(self) -> None:
        self.events.append("terminate")

    def wait(self, timeout: float | None = None) -> int:
        if self.stubborn and "kill" not in self.events:
            raise subprocess.TimeoutExpired("zathura", timeout or 0)
        self.events.append("wait")
        return 0

    def kill(self) -> None:
        self.events.append("kill")


class Bus:
    """Stands in for ``gdbus``: records calls, answers like Zathura's D-Bus object."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.page = 3
        self.reply_ok = True
        self.returncode = 0

    def __call__(self, cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(cmd)
        method = cmd[cmd.index("--method") + 1]
        if method.endswith("Properties.Get"):
            out = f"(<uint32 {self.page}>,)\n"
        else:
            out = "(true,)\n" if self.reply_ok else "(false,)\n"
        return subprocess.CompletedProcess(cmd, self.returncode, out if not self.returncode else "", "bus error")


@pytest.fixture
def running(monkeypatch: pytest.MonkeyPatch) -> tuple[Zathura, FakeProc, Bus]:
    proc, bus = FakeProc(), Bus()
    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: proc)
    monkeypatch.setattr(subprocess, "run", bus)
    viewer = Zathura(Path("/tmp/x.pdf"))
    viewer.start()
    return viewer, proc, bus


def test_start_waits_for_the_bus_and_commands_go_to_the_pid_name(running: tuple[Zathura, FakeProc, Bus]) -> None:
    viewer, _proc, bus = running
    viewer.goto(5)
    assert viewer.page() == 3
    assert any("org.pwmt.zathura.PID-4242" in part for part in bus.calls[-1])
    assert bus.calls[-2][-4:-2] == ["--method", "org.pwmt.zathura.GotoPage"] or "GotoPage" in " ".join(bus.calls[-2])


def test_goto_and_fullscreen_report_rejections(running: tuple[Zathura, FakeProc, Bus]) -> None:
    viewer, _proc, bus = running
    bus.reply_ok = False
    with pytest.raises(ProjectorError, match="rejected page 2"):
        viewer.goto(2)
    with pytest.raises(ProjectorError, match="fullscreen"):
        viewer.fullscreen(True)
    bus.reply_ok = True
    viewer.fullscreen(True)
    assert viewer.is_fullscreen() is True
    viewer.fullscreen(False)
    assert viewer.is_fullscreen() is False


def test_bus_errors_become_projector_errors(
    running: tuple[Zathura, FakeProc, Bus], monkeypatch: pytest.MonkeyPatch
) -> None:
    viewer, _proc, bus = running
    bus.returncode = 1
    with pytest.raises(ProjectorError, match="bus error"):
        viewer.page()
    bus.returncode = 0

    def boom(*_a: object, **_k: object) -> None:
        raise OSError("no gdbus")

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(ProjectorError, match="no gdbus"):
        viewer.page()


def test_unexpected_reply_to_the_page_query(
    running: tuple[Zathura, FakeProc, Bus], monkeypatch: pytest.MonkeyPatch
) -> None:
    viewer, _proc, _bus = running
    monkeypatch.setattr(subprocess, "run", lambda cmd, **_k: subprocess.CompletedProcess(cmd, 0, "(<'text'>,)\n", ""))
    with pytest.raises(ProjectorError, match="unexpected reply"):
        viewer.page()


def test_commands_need_a_running_window() -> None:
    with pytest.raises(ProjectorError, match="not running"):
        Zathura(Path("/tmp/x.pdf")).goto(1)


def test_cannot_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise OSError("no zathura")

    monkeypatch.setattr(subprocess, "Popen", boom)
    with pytest.raises(ProjectorError, match="cannot launch zathura"):
        Zathura(Path("/tmp/x.pdf")).start()


def test_start_gives_up_when_the_bus_never_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = FakeProc()
    bus = Bus()
    bus.returncode = 1
    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: proc)
    monkeypatch.setattr(subprocess, "run", bus)
    monkeypatch.setattr(zathura, "STARTUP_TIMEOUT_S", 0.3)
    monkeypatch.setattr(zathura, "STARTUP_POLL_S", 0.05)
    with pytest.raises(ProjectorError, match="did not appear on D-Bus"):
        Zathura(Path("/tmp/x.pdf")).start()
    assert "terminate" in proc.events  # the half-started window is closed again


def test_stop_is_polite_then_firm_and_idempotent(running: tuple[Zathura, FakeProc, Bus]) -> None:
    viewer, proc, _bus = running
    viewer.stop()
    assert proc.events == ["terminate", "wait"]
    viewer.stop()  # already stopped: nothing more happens
    assert proc.events == ["terminate", "wait"]


def test_stop_kills_a_window_that_ignores_terminate(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = FakeProc(stubborn=True)
    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: proc)
    monkeypatch.setattr(subprocess, "run", Bus())
    viewer = Zathura(Path("/tmp/x.pdf"))
    viewer.start()
    viewer.stop()
    assert proc.events[:2] == ["terminate", "kill"]


def test_stop_leaves_an_already_closed_window_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = FakeProc()
    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: proc)
    monkeypatch.setattr(subprocess, "run", Bus())
    viewer = Zathura(Path("/tmp/x.pdf"))
    viewer.start()
    proc.alive = False  # the user closed the projector window
    viewer.stop()
    assert proc.events == []
