from pathlib import Path

import cairo

from lectos import render
from lectos.deck import Deck
from lectos.ink import Ink, slide_layer
from lectos.paths import unique
from lectos.stage import Stage


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
