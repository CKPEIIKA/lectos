from pathlib import Path

import pytest

from lectos.notes import beamer
from lectos.notes.markdown import MarkdownNotes

TEX = r"""
\begin{document}
% \note{commented out}
\begin{frame}{One}
Hello
\note{first \textbf{bold} and $a^2$}
\end{frame}
\begin{frame}[fragile]
\frametitle{Two \alert{!}}
\begin{itemize}[<+->]\item a \item b\end{itemize}
\end{frame}
\note<2>[x]{between frames, belongs to Two \\ more}
\begin{frame}<1->{Three}
\note{third {nested {braces}}}
\note{third again}
\end{frame}
"""

NAV = r"""
\headcommand {\beamer@framepages {1}{1}}
\headcommand {\beamer@framepages {2}{4}}
\headcommand {\beamer@framepages {5}{5}}
"""
FIRST, SECOND, THIRD = 1, 4 - 2, 5


def test_scan_finds_frames_titles_notes_and_ignores_comments() -> None:
    found = beamer.scan(TEX)
    assert found.frames == 3
    assert [(n.frame, n.text.split()[0]) for n in found.notes] == [
        (0, "first"),
        (1, "between"),
        (2, "third"),
        (2, "third"),
    ]
    assert found.titles == {0: "One", 1: r"Two \alert{!}", 2: "Three"}
    assert "nested {braces}" in found.notes[2].text


def test_frame_pages_follow_overlays() -> None:
    assert beamer.frame_pages(NAV) == [(1, 1), (2, 4), (5, 5)]


def test_sections_use_nav_pages_and_merge_notes_per_frame() -> None:
    secs = beamer.sections(TEX, NAV)
    assert [s.slide for s in secs] == [FIRST, SECOND, THIRD]
    assert secs[0].text.startswith("## One\n\nfirst **bold** and $a^2$")
    assert "belongs to Two\nmore" in secs[1].text
    assert secs[2].text.count("third") == 2


def test_sections_without_nav_assume_one_page_per_frame() -> None:
    assert [s.slide for s in beamer.sections(TEX, None)] == [1, 2, 3]


def test_to_markdown_items_and_formatting() -> None:
    raw = r"\begin{itemize}\item one \emph{two} \item \texttt{x} \pause\end{itemize}"
    assert beamer.to_markdown(raw) == "- one *two*\n- `x`"


def test_open_notes_chooses_source_by_suffix(tmp_path: Path) -> None:
    tex, md, pdf = tmp_path / "a.tex", tmp_path / "a.md", tmp_path / "a.pdf"
    tex.write_text(TEX)
    md.write_text("x")
    assert isinstance(beamer.open_notes(md, pdf), MarkdownNotes)
    source = beamer.open_notes(tex, pdf)
    assert isinstance(source, beamer.BeamerNotes)
    assert [s.slide for s in source.load()] == [1, 2, 3]
    (tmp_path / "a.nav").write_text(NAV)  # picked up once it exists
    assert [s.slide for s in source.load()] == [FIRST, SECOND, THIRD]
    assert source.stamp() > 0


def test_sample_deck_notes_match_pages() -> None:
    root = Path(__file__).resolve().parents[2] / "examples"
    tex_sections = beamer.sections((root / "slides.tex").read_text(), None)
    assert [s.slide for s in tex_sections] == list(range(1, 9))
    md = MarkdownNotes(root / "notes.md").load()
    assert [s.slide for s in md if s.slide] == list(range(1, 9))


def test_unreadable_tex_raises(tmp_path: Path) -> None:
    from lectos.notes.markdown import NotesError

    with pytest.raises(NotesError):
        beamer.BeamerNotes(tmp_path / "missing.tex", []).load()


def test_to_markdown_text_symbols() -> None:
    assert (
        beamer.to_markdown(r"\texttt{\textbackslash note} 50\% of A\&B in \texttt{\textasciitilde/x}")
        == "`\\note` 50% of A&B in `~/x`"
    )


def test_unbalanced_note_braces_are_ignored() -> None:
    found = beamer.scan("\\begin{frame}\\note{never closed")
    assert found.notes == []
    assert found.frames == 1


def test_oversized_tex_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from lectos.notes.markdown import NotesError

    tex = tmp_path / "big.tex"
    tex.write_text("x" * 50)
    monkeypatch.setattr(beamer, "MAX_NOTES_BYTES", 10)
    with pytest.raises(NotesError, match="exceeds"):
        beamer.BeamerNotes(tex, []).load()
