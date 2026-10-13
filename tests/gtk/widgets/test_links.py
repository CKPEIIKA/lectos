import pytest
from gi.repository import Gdk, GLib, Gtk

from lectos.draw.stage import Stage
from lectos.gtk.pdfdoc import PdfDoc
from lectos.gtk.widgets import links as links_module
from lectos.gtk.widgets.links import LinkInput, launch
from lectos.model.deck import Deck
from lectos.model.ink import Ink

LINKS = [
    {"links": [((100, 100, 300, 200), 1), ((20, 250, 120, 290), "https://example.org")]},
    {},
]


class Device:
    def __init__(self, source: Gdk.InputSource) -> None:
        self.source = source

    def get_source(self) -> Gdk.InputSource:
        return self.source


class Gesture:
    def __init__(self, device: Device | None = None) -> None:
        self.device = device

    def get_current_event_device(self) -> Device | None:
        return self.device


@pytest.fixture
def rig_links(pdf_maker):
    doc = PdfDoc(pdf_maker(LINKS))
    deck, ink = Deck(doc.pages), Ink()
    stage = Stage(doc, deck, ink)
    area = Gtk.DrawingArea()
    area.get_width = lambda: 400  # the area shows the 400x300 slide at scale 1
    area.get_height = lambda: 300
    went: list[int] = []
    opened: list[str] = []
    return LinkInput(area, stage, ink, lambda: deck.view, on_page=went.append, on_uri=opened.append), went, opened


def test_a_click_on_a_page_link_goes_there_and_on_an_address_link_opens_it(rig_links) -> None:
    link_input, went, opened = rig_links
    link_input._released(Gesture(), 1, 200.0, 150.0)  # the PDF rect (100,100)-(300,200) sits at y 100..200
    link_input._released(Gesture(), 1, 50.0, 30.0)
    link_input._released(Gesture(), 1, 390.0, 290.0)  # nothing there
    assert (went, opened) == ([1], ["https://example.org"])


def test_a_pen_stroke_is_not_a_click(rig_links) -> None:
    link_input, went, _opened = rig_links
    link_input._released(Gesture(Device(Gdk.InputSource.PEN)), 1, 200.0, 150.0)
    assert went == []
    link_input._released(Gesture(Device(Gdk.InputSource.MOUSE)), 1, 200.0, 150.0)
    assert went == [1]


def test_links_are_off_while_drawing_on_the_board_or_off_the_deck(rig_links) -> None:
    link_input, _went, _opened = rig_links
    assert link_input.link_at(200.0, 150.0) is not None
    link_input.ink.tool.mouse_draw = True
    assert link_input.link_at(200.0, 150.0) is None
    link_input.ink.tool.mouse_draw = False
    link_input.stage.deck.board = True
    assert link_input.link_at(200.0, 150.0) is None
    link_input.stage.deck.board = False
    link_input.stage.deck.view = 5  # not a page of the deck
    assert link_input.link_at(200.0, 150.0) is None


def test_the_pointer_changes_over_links_only(rig_links) -> None:
    link_input, _went, _opened = rig_links
    link_input._moved(None, 200.0, 150.0)
    assert link_input.area.get_cursor().get_name() == "pointer"
    link_input._moved(None, 200.0, 150.0)  # still over it
    link_input._moved(None, 390.0, 290.0)
    assert link_input.area.get_cursor() is None
    link_input._show_pointer(False)  # leaving when not over one changes nothing


def test_launching_only_opens_safe_addresses(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(links_module.Gio.AppInfo, "launch_default_for_uri", lambda uri, _ctx: opened.append(uri))
    assert launch("https://example.org") == ""
    assert opened == ["https://example.org"]
    assert "only http, https and mailto" in launch("file:///etc/passwd")
    assert opened == ["https://example.org"]

    def refuse(_uri: str, _ctx: object) -> None:
        raise GLib.Error("no browser installed")

    monkeypatch.setattr(links_module.Gio.AppInfo, "launch_default_for_uri", refuse)
    assert "no browser installed" in launch("mailto:a@b.c")
