from pathlib import Path

import pytest

from lectos.notes import markdown
from lectos.notes.markdown import Span, parse


def test_parse_headings_emphasis_bullets() -> None:
    spans = parse("# Title\nsome **bold** and *it* and `c`\n- item\n")
    assert Span("Title\n", "h1") in spans
    assert Span("bold", "bold") in spans
    assert Span("it", "italic") in spans
    assert Span("c", "code") in spans
    assert any("• item" in s.text for s in spans)


def test_parse_math_variants() -> None:
    spans = parse("inline $a^2$ and $$\nx=1\n$$ and \\[y=2\\] cost $5 and $6")
    assert [(s.text, s.style) for s in spans if s.style in ("math", "display")] == [
        ("a^2", "math"),
        ("x=1", "display"),
        ("y=2", "display"),
    ]


def test_math_not_formatted_as_emphasis() -> None:
    spans = parse("$a*b*c$")
    assert spans == [Span("a*b*c", "math")]


def test_oversized_and_missing_notes_files_raise_notes_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    big = tmp_path / "big.md"
    big.write_text("x" * 50)
    monkeypatch.setattr(markdown, "MAX_NOTES_BYTES", 10)
    with pytest.raises(markdown.NotesError, match="exceeds"):
        markdown.load_sections(big)
    with pytest.raises(markdown.NotesError, match="cannot read"):
        markdown.load_sections(tmp_path / "missing.md")


def test_split_markdown_assigns_slides_from_markers() -> None:
    text = "intro\n<!-- slide: 2 -->\n## A\n<!-- slide: 3 -->\nB\n"
    assert markdown.split_markdown(text) == [(None, "intro\n"), (2, "\n## A\n"), (3, "\nB\n")]


MARKED = "intro\n<!-- slide: 1 -->\none\n<!-- slide: 2 -->\ntwo\n"


def test_replacing_a_section_keeps_its_neighbours() -> None:
    assert markdown.replace_section(MARKED, 1, "ONE\n\n") == "intro\n<!-- slide: 1 -->\nONE\n\n<!-- slide: 2 -->\ntwo\n"
    assert markdown.replace_section(MARKED, 2, "TWO") == "intro\n<!-- slide: 1 -->\none\n<!-- slide: 2 -->\nTWO\n"


def test_a_slide_without_notes_gets_a_new_marker_at_the_end() -> None:
    assert markdown.replace_section(MARKED, 5, "five") == MARKED + "\n<!-- slide: 5 -->\nfive\n"
    assert markdown.replace_section("", 1, "a") == "\n<!-- slide: 1 -->\na\n"
    assert markdown.replace_section("no newline", 3, "b") == "no newline\n\n<!-- slide: 3 -->\nb\n"


def test_markdown_notes_are_rewritten_in_place(tmp_path: Path) -> None:
    path = tmp_path / "n.md"
    path.write_text(MARKED)
    source = markdown.MarkdownNotes(path)
    source.save(2, "second")
    assert [(s.slide, s.text.strip()) for s in source.load()] == [(None, "intro"), (1, "one"), (2, "second")]


def test_saving_notes_that_cannot_be_written_is_a_notes_error(tmp_path: Path) -> None:
    with pytest.raises(markdown.NotesError, match="cannot write"):
        markdown.MarkdownNotes(tmp_path / "missing.md").save(1, "x")
