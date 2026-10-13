"""Zathura as the projector for the terminal console: launched and driven over D-Bus with gdbus."""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

GDBUS_TIMEOUT_S = 5.0
STARTUP_TIMEOUT_S = 10.0
STARTUP_POLL_S = 0.1
OBJECT_PATH = "/org/pwmt/zathura"
INTERFACE = "org.pwmt.zathura"
_UINT_RE = re.compile(r"uint32 (\d+)")


class ProjectorError(RuntimeError):
    """Raised when the projector cannot be launched or controlled."""


class Zathura:
    """A Zathura window owned by this process, addressed by its PID bus name."""

    caps: frozenset[str] = frozenset()  # no blackout, chalkboard, ink or laser: it is a plain PDF viewer

    def __init__(self, pdf: Path) -> None:
        self._pdf = pdf
        self._full = False
        self._proc: subprocess.Popen[bytes] | None = None

    def _call(self, method: str, *args: str) -> str:
        if self._proc is None or self._proc.poll() is not None:
            raise ProjectorError("projector window is not running")
        cmd = [
            "gdbus", "call", "--session", "--dest", f"org.pwmt.zathura.PID-{self._proc.pid}",
            "--object-path", OBJECT_PATH, "--method", method, *args,
        ]  # fmt: skip
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=GDBUS_TIMEOUT_S, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProjectorError(f"gdbus failed: {exc}") from exc
        if result.returncode != 0:
            raise ProjectorError(f"gdbus failed: {result.stderr.strip()}")
        return result.stdout

    def start(self) -> None:
        """Launch Zathura on the PDF and wait until its D-Bus object answers."""
        try:
            self._proc = subprocess.Popen(["zathura", "--", str(self._pdf)], stderr=subprocess.DEVNULL)
        except OSError as exc:
            raise ProjectorError(f"cannot launch zathura: {exc}") from exc
        deadline = time.monotonic() + STARTUP_TIMEOUT_S
        while time.monotonic() < deadline:
            try:
                self.page()
            except ProjectorError:
                time.sleep(STARTUP_POLL_S)
            else:
                return
        self.stop()
        raise ProjectorError("zathura did not appear on D-Bus")

    def stop(self) -> None:
        """Terminate the owned Zathura process."""
        proc, self._proc = self._proc, None
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=GDBUS_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    def page(self) -> int:
        """Current zero-based page."""
        out = self._call("org.freedesktop.DBus.Properties.Get", INTERFACE, "pagenumber")
        match = _UINT_RE.search(out)
        if match is None:
            raise ProjectorError(f"unexpected reply: {out.strip()}")
        return int(match.group(1))

    def goto(self, page: int) -> None:
        """Show the zero-based page."""
        if "true" not in self._call(f"{INTERFACE}.GotoPage", str(page)):
            raise ProjectorError(f"zathura rejected page {page}")

    def fullscreen(self, on: bool) -> None:
        """Set Zathura's fullscreen option."""
        if "true" not in self._call(f"{INTERFACE}.ExecuteCommand", f"set fullscreen {'true' if on else 'false'}"):
            raise ProjectorError("zathura rejected the fullscreen setting")
        self._full = on

    def is_fullscreen(self) -> bool:
        """Last fullscreen state set through this object."""
        return self._full
