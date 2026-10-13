from pathlib import Path

import cairo
import pytest

from lectos.draw import render
from lectos.draw.stage import Stage
from lectos.model.deck import Deck
from lectos.model.ink import Ink, slide_layer
from lectos.model.links import Link
from lectos.paths import unique


def test_unique_never_returns_an_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "a-annotated.pdf"
    assert unique(target) == target
    target.write_bytes(b"x")
    assert unique(target) == tmp_path / "a-annotated-2.pdf"
    (tmp_path / "a-annotated-2.pdf").write_bytes(b"x")
    assert unique(target) == tmp_path / "a-annotated-3.pdf"


class FakeDoc:
    def page_size(self, page: int) -> tuple[float, float]:
        return 200.0, 100.0

    def links(self, page: int) -> list[Link]:
        return []

    def paint(self, cr: cairo.Context, page: int) -> None:
        cr.set_source_rgb(1, 1, 1)
        cr.paint()

    def draw(self, cr: cairo.Context, page: int, width: int, height: int) -> tuple[float, float, float]:
        return render.fit(200.0, 100.0, width, height)


def test_export_writes_one_page_per_slide_plus_board_with_ink(tmp_path: Path) -> None:
    deck, ink = Deck(3), Ink()
    stage = Stage(FakeDoc(), deck, ink)
    plain = tmp_path / "plain.pdf"
    assert stage.export_pdf(plain) == 3
    ink.begin(slide_layer(1), 10.0, 10.0, 1.0)
    ink.extend(slide_layer(1), 90.0, 40.0, 1.0)
    ink.begin("board", 10.0, 10.0, 1.0)
    ink.extend("board", 500.0, 300.0, 1.0)
    annotated = tmp_path / "annotated.pdf"
    assert stage.export_pdf(annotated) == 4
    for path in (plain, annotated):
        assert path.read_bytes().startswith(b"%PDF-")
    assert annotated.stat().st_size > plain.stat().st_size


def test_restore_cleared_brings_back_only_the_last_clear_all() -> None:
    ink = Ink()
    ink.begin("s0", 0.0, 0.0, 1.0)
    ink.begin("board", 0.0, 0.0, 1.0)
    assert ink.clear_all() == 2
    assert sorted(ink.last_cleared) == ["board", "s0"]
    assert ink.restore_cleared() == 2
    assert len(ink.strokes("s0")) == len(ink.strokes("board")) == 1
    assert ink.restore_cleared() == 0


def test_unique_gives_up_when_every_name_is_taken(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from lectos import paths

    monkeypatch.setattr(paths, "MAX_TRIES", 4)
    target = tmp_path / "a.pdf"
    for name in ("a.pdf", "a-2.pdf", "a-3.pdf"):
        (tmp_path / name).write_bytes(b"x")
    with pytest.raises(OSError, match="no free name"):
        unique(target)


def test_notes_are_found_next_to_the_slides(tmp_path: Path) -> None:
    from lectos.paths import notes_for

    pdf = tmp_path / "talk.pdf"
    assert notes_for(pdf) is None
    (tmp_path / "notes.md").write_text("x")
    assert notes_for(pdf) == tmp_path / "notes.md"
    (tmp_path / "talk.md").write_text("x")
    assert notes_for(pdf) == tmp_path / "talk.md"
    (tmp_path / "talk.tex").write_text("x")
    assert notes_for(pdf) == tmp_path / "talk.tex"  # Beamer source first


def test_a_folder_gives_the_slides_that_have_notes(tmp_path: Path) -> None:
    from lectos.paths import discover

    assert discover(tmp_path) is None
    (tmp_path / "a.pdf").write_bytes(b"%PDF-")
    assert discover(tmp_path) == (tmp_path / "a.pdf", None)
    (tmp_path / "b.pdf").write_bytes(b"%PDF-")
    (tmp_path / "b.md").write_text("x")
    assert discover(tmp_path) == (tmp_path / "b.pdf", tmp_path / "b.md")


def test_write_atomic_replaces_and_cleans_up_after_a_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    from lectos import paths

    target = tmp_path / "deep" / "f.txt"
    paths.write_atomic(target, "one")
    paths.write_atomic(target, "two")
    assert target.read_text() == "two"

    def refuse(*_a: object) -> None:
        raise OSError("no")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(OSError, match="no"):
        paths.write_atomic(target, "three")
    assert target.read_text() == "two"
    assert [p.name for p in target.parent.iterdir()] == ["f.txt"]


def test_the_drawing_layer_alone_is_written_as_a_transparent_png(tmp_path: Path) -> None:
    deck, ink = Deck(2), Ink()
    stage = Stage(FakeDoc(), deck, ink)
    ink.begin(slide_layer(0), 20.0, 20.0, 1.0)
    ink.extend(slide_layer(0), 150.0, 60.0, 1.0)
    out = tmp_path / "ink.png"
    stage.export_ink_png(out, 0)
    surface = cairo.ImageSurface.create_from_png(str(out))
    assert surface.get_width() >= 1920
    data = bytes(surface.get_data())
    assert any(data[3::4]) and not all(data[3::4])  # some pixels drawn, the rest transparent
