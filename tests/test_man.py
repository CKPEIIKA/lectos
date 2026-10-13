import re
import shutil
import subprocess
from pathlib import Path

import pytest

from lectos import cli

MAN = Path(__file__).parent.parent / "man"


def long_options() -> set[str]:
    return {
        opt for action in cli.build_parser("lectos")._actions for opt in action.option_strings if opt.startswith("--")
    }


@pytest.mark.parametrize("page", ["lectos", "lectos-tui"])
def test_man_pages_exist_and_are_roff(page: str) -> None:
    text = (MAN / f"{page}.1").read_text(encoding="utf-8")
    assert text.startswith(".")
    assert page in text.replace("\\-", "-")  # roff writes hyphens as \\-


def test_man_page_documents_every_command_line_option() -> None:
    source = (MAN / "lectos.1.scd").read_text(encoding="utf-8")
    documented = set(re.findall(r"\*(--[a-z-]+)\*", source))
    assert long_options() - {"--help"} <= documented
    assert documented <= long_options() | {"--help"}


@pytest.mark.skipif(shutil.which("scdoc") is None, reason="needs scdoc")
@pytest.mark.parametrize("page", ["lectos", "lectos-tui"])
def test_generated_roff_is_up_to_date_with_its_source(page: str) -> None:
    built = subprocess.run(
        ["scdoc"], input=(MAN / f"{page}.1.scd").read_text(encoding="utf-8"), capture_output=True, text=True, check=True
    ).stdout
    # scdoc stamps the date into the header, so compare everything but that line
    strip = lambda t: "\n".join(line for line in t.splitlines() if not line.startswith(".TH"))  # noqa: E731
    assert strip(built) == strip((MAN / f"{page}.1").read_text(encoding="utf-8"))


def test_license_file_is_the_plain_gpl3_text() -> None:
    text = (MAN.parent / "LICENSE").read_text(encoding="utf-8")
    assert text.lstrip().startswith("GNU GENERAL PUBLIC LICENSE")
    assert "Version 3, 29 June 2007" in text
