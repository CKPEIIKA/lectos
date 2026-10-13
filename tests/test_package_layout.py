from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAX_PY_FILES = 7  # AGENTS.md: keep package folders compact; beyond this, consolidate or add a coherent subpackage
SKIP = {"__pycache__", "locale", "icons"}  # data folders


def folders(top: str) -> list[Path]:
    base = ROOT / top
    found = [base] + [p for p in base.rglob("*") if p.is_dir() and not (set(p.parts) & SKIP)]
    return sorted(found)


@pytest.mark.parametrize("top", ["lectos", "tests"])
def test_no_folder_holds_more_than_seven_python_files(top: str) -> None:
    too_big = {
        str(p.relative_to(ROOT)): len(list(p.glob("*.py")))
        for p in folders(top)
        if len(list(p.glob("*.py"))) > MAX_PY_FILES
    }
    assert too_big == {}


def test_every_package_folder_has_an_init_and_no_stray_modules_remain_at_the_top() -> None:
    for folder in folders("lectos"):
        assert (folder / "__init__.py").exists(), folder
    top_level = {p.stem for p in (ROOT / "lectos").glob("*.py")}
    assert top_level == {"__init__", "__main__", "cli", "config", "i18n", "paths", "state"}
