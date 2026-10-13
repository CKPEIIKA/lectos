import os

import cairo
import pytest

from lectos.gtk.pdfdoc import AnnotationNotes, PdfDoc
from lectos.model.links import Link
from lectos.notes.markdown import NotesError

SPLIT = {"size": (800, 300), "text": "SLIDEWORD", "text_right": "NOTEWORD"}


def pixels(draw, width: int = 200, height: int = 100) -> bytes:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    draw(cairo.Context(surface), width, height)
    surface.flush()
    return bytes(surface.get_data())


def test_plain_pages_are_not_split(pdf_maker) -> None:
    doc = PdfDoc(pdf_maker([{}]))
    assert doc.notes_side == ""
    assert doc.page_size(0) == (400, 300)
    assert not any(pixels(lambda cr, w, h: doc.draw_notes(cr, 0, w, h)))  # nothing to show


def test_wide_pages_are_slide_plus_notes_with_the_notes_on_the_right(pdf_maker) -> None:
    doc = PdfDoc(pdf_maker([SPLIT]))
    assert doc.notes_side == "right"
    assert doc.page_size(0) == (400, 300)
    assert "SLIDEWORD" in doc.texts()[0]
    assert "NOTEWORD" not in doc.texts()[0]  # searching never finds the notes half
    assert any(pixels(lambda cr, w, h: doc.draw_notes(cr, 0, w, h)))
    assert pixels(lambda cr, w, h: doc.draw(cr, 0, w, h)) != pixels(lambda cr, w, h: doc.draw_notes(cr, 0, w, h))


def test_the_notes_side_can_be_chosen_or_switched_off(pdf_maker) -> None:
    path = pdf_maker([SPLIT])
    left = PdfDoc(path, "left")
    assert left.notes_side == "left"
    assert "NOTEWORD" in left.texts()[0]  # the right half is the slide when the notes are on the left
    assert "SLIDEWORD" not in left.texts()[0]
    assert PdfDoc(path, "none").page_size(0) == (800, 300)
    assert PdfDoc(path, "right").notes_side == "right"


def test_links_are_flipped_to_the_top_left_origin(pdf_maker) -> None:
    path = pdf_maker([{"links": [((20, 200, 120, 240), "https://example.org"), ((200, 20, 300, 60), 1)]}, {}])
    doc = PdfDoc(path)
    links = doc.links(0)
    assert Link(20, 60, 100, 40, None, "https://example.org") in links
    assert Link(200, 240, 100, 40, 1, "") in links
    assert doc.links(0) is links  # read once


def test_named_destinations_resolve_and_other_actions_are_ignored(pdf_maker) -> None:
    path = pdf_maker(
        [
            {
                "links": [
                    ((10, 10, 50, 50), ("named", "chapter")),
                    ((60, 10, 100, 50), ("named", "missing")),
                    ((110, 10, 150, 50), "next"),
                ]
            },
            {},
        ],
        names={"chapter": 1},
    )
    assert [(link.page, link.uri) for link in PdfDoc(path).links(0)] == [(1, "")]


def test_links_on_the_notes_half_are_not_slide_links(pdf_maker) -> None:
    page = {
        "size": (800, 300),
        "links": [((20, 20, 60, 60), "https://slide.example"), ((420, 20, 460, 60), "https://notes.example")],
    }
    assert [link.uri for link in PdfDoc(pdf_maker([page])).links(0)] == ["https://slide.example"]
    shifted = PdfDoc(pdf_maker([page], name="l.pdf"), "left")  # now the right half is the slide
    assert [(link.uri, link.x) for link in shifted.links(0)] == [("https://notes.example", 20)]


def test_note_annotations_are_collected_per_slide(pdf_maker) -> None:
    path = pdf_maker(
        [
            {
                "notes": [((10, 10, 30, 30), "remember the proof"), ((40, 10, 60, 30), "")],
                "links": [((70, 10, 90, 30), 1)],
            },
            {},
            {"notes": [((10, 10, 30, 30), "third")]},
        ]
    )
    doc = PdfDoc(path)
    assert doc.annotations() == {0: ["remember the proof"], 2: ["third"]}
    assert doc.annotations() is doc.annotations()


def test_annotations_on_the_notes_half_belong_to_the_notes_not_the_slide(pdf_maker) -> None:
    page = {
        "size": (800, 300),
        "notes": [((10, 10, 30, 30), "on the slide"), ((410, 10, 430, 30), "on the notes page")],
    }
    assert PdfDoc(pdf_maker([page])).annotations() == {0: ["on the slide"]}


def test_annotations_make_read_only_notes(pdf_maker) -> None:
    path = pdf_maker([{"notes": [((10, 10, 30, 30), "first")]}, {}])
    doc = PdfDoc(path)
    source = AnnotationNotes(doc)
    assert [(s.slide, s.text.strip()) for s in source.load()] == [(1, "first")]
    before = source.stamp()
    with pytest.raises(NotesError, match="read only"):
        source.save(1, "x")
    pdf_maker([{"notes": [((10, 10, 30, 30), "changed")]}, {}])
    os.utime(path, ns=(5, 5))
    assert doc.refresh() is True
    assert source.stamp() != before
    assert [s.text.strip() for s in source.load()] == ["changed"]


def test_reloading_forgets_links_and_looks_at_the_pages_again(pdf_maker) -> None:
    path = pdf_maker([{"links": [((10, 10, 50, 50), "https://a.example")]}])
    doc = PdfDoc(path)
    assert doc.links(0)
    assert doc.notes_side == ""
    pdf_maker([SPLIT])
    os.utime(path, ns=(7, 7))
    assert doc.refresh() is True
    assert doc.notes_side == "right"  # the deck was rebuilt with notes pages
    assert doc.links(0) == []
