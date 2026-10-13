import importlib.util
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from lectos import config, i18n
from lectos.control import commands, keys

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location("marked_strings", ROOT / "scripts" / "marked_strings.py")
assert _spec is not None
assert _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
marked = _module.marked

LOCALES = ROOT / "lectos" / "locale"
PO_FILES = sorted(LOCALES.glob("*.po"))
PO_IDS = [p.stem for p in PO_FILES]
PLACEHOLDER = re.compile(r"\{[^{}]*\}")


@pytest.fixture(autouse=True)
def reset_language():
    yield
    i18n.init("en")


def test_parse_po_handles_continuations_escapes_and_untranslated() -> None:
    text = (
        '# comment\nmsgid ""\nmsgstr ""\n"Language: ru\\n"\n\n'
        'msgid "Hello"\nmsgstr "Привет"\n\n'
        'msgid "Two "\n"lines"\nmsgstr "Две "\n"строки"\n\n'
        'msgid "Quote \\"x\\"\\nnext"\nmsgstr "Кавычка \\"x\\"\\nдалее"\n\n'
        'msgid "Untranslated"\nmsgstr ""\n'
    )
    assert i18n.parse_po(text) == {
        "Hello": "Привет",
        "Two lines": "Две строки",
        'Quote "x"\nnext': 'Кавычка "x"\nдалее',
    }


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"LANG": "ru_RU.UTF-8"}, "ru"),
        ({"LANG": "de_DE.UTF-8"}, "de"),
        ({"LANG": "en_US.UTF-8"}, "en"),
        ({"LANGUAGE": "ru:en", "LANG": "en_US.UTF-8"}, "ru"),
        ({"LC_ALL": "ru_RU.UTF-8", "LANG": "en_US.UTF-8"}, "ru"),
        ({"LANG": "fr_FR.UTF-8"}, "en"),
        ({}, "en"),
    ],
)
def test_detect_reads_the_environment(monkeypatch: pytest.MonkeyPatch, env: dict[str, str], expected: str) -> None:
    for name in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert i18n.detect() == expected
    assert i18n.init("auto") == expected


def test_init_selects_language_and_falls_back_to_the_original_text() -> None:
    assert i18n.init("ru") == "ru"
    assert i18n.tr("Overview") == "Обзор"
    assert i18n.tr("not marked anywhere") == "not marked anywhere"
    assert i18n.init("en") == "en"
    assert i18n.tr("Overview") == "Overview"
    assert i18n.init("klingon") == "en"


def test_every_language_has_a_catalog_file() -> None:
    assert sorted(set(i18n.LANGUAGES) - {"en"}) == sorted(PO_IDS)


@pytest.mark.parametrize("po", PO_FILES, ids=PO_IDS)
def test_every_marked_string_is_translated_and_nothing_is_stale(po: Path) -> None:
    catalog = i18n.parse_po(po.read_text(encoding="utf-8"))
    strings = marked(ROOT / "lectos")
    assert [m for m in strings if m not in catalog] == []
    assert [k for k in catalog if k not in strings] == []


@pytest.mark.parametrize("po", PO_FILES, ids=PO_IDS)
def test_translations_keep_the_same_placeholders(po: Path) -> None:
    for original, translated in i18n.parse_po(po.read_text(encoding="utf-8")).items():
        assert sorted(PLACEHOLDER.findall(original)) == sorted(PLACEHOLDER.findall(translated)), original


@pytest.mark.skipif(shutil.which("msgfmt") is None, reason="needs msgfmt")
@pytest.mark.parametrize("po", PO_FILES, ids=PO_IDS)
def test_catalog_is_a_valid_gettext_file(po: Path) -> None:
    result = subprocess.run(
        ["msgfmt", "-c", "--check-format", "-o", "/dev/null", str(po)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("po", PO_FILES, ids=PO_IDS)
def test_translations_differ_from_english_for_most_entries(po: Path) -> None:
    catalog = i18n.parse_po(po.read_text(encoding="utf-8"))
    same = [k for k, v in catalog.items() if k == v]
    assert len(same) < len(catalog) * 0.15  # a few (px, {n}, command names) legitimately stay the same


def test_german_selection_and_text() -> None:
    assert i18n.init("de") == "de"
    assert i18n.tr("Overview") == "Übersicht"
    assert "Zu Folie N gehen" in commands.describe("goto", keys.key_for)
    assert "[Taste l]" in commands.describe("next", keys.key_for)
    assert "kein solcher Befehl" in commands.describe("nonsense", keys.key_for)


def test_help_and_messages_come_out_in_russian() -> None:
    i18n.init("ru")
    assert "Перейти к слайду" in commands.describe("goto", keys.key_for)
    assert "нет такой команды" in commands.describe("nonsense", keys.key_for)
    assert "[клавиша l]" in commands.describe("next", keys.key_for)


def test_language_option(tmp_path: Path) -> None:
    path = tmp_path / "o.toml"
    path.write_text('[ui]\nlanguage = "de"\n')
    assert config.load(path).language == "de"
    assert config.Options().language == "auto"
    path.write_text('[ui]\nlanguage = "xx"\n')
    with pytest.raises(config.ConfigError):
        config.load(path)
