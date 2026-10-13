"""Shared test setup: every test gets private state, cache and config directories."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_user_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Never read or write the presenter's real recovery state, caches or options."""
    for name in ("XDG_STATE_HOME", "XDG_CACHE_HOME", "XDG_CONFIG_HOME"):
        monkeypatch.setenv(name, str(tmp_path / name.lower()))
