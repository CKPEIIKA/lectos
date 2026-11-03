import cairo
import pytest

from lectos.draw import render
from lectos.draw.stage import Stage
from lectos.model.deck import Deck
from lectos.model.ink import COLORS, Ink, Stroke, slide_layer
from lectos.model.links import Link
from lectos.model.style import BOARD_STYLES, LaserStyle

PAGE_W, PAGE_H = 400.0, 300.0


class FakeDoc:
    def page_size(self, page: int) -> tuple[float, float]:
        return PAGE_W, PAGE_H

    def links(self, page: int) -> list[Link]:
        return []

    def paint(self, cr: cairo.Context, page: int) -> None:
        cr.set_source_rgb(1, 1, 1)
        cr.paint()

    def draw(self, cr: cairo.Context, page: int, width: int, height: int) -> tuple[float, float, float]:
        fit = render.fit(PAGE_W, PAGE_H, width, height)
        cr.translate(fit[1], fit[2])
        cr.scale(fit[0], fit[0])
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(0, 0, PAGE_W, PAGE_H)
        cr.fill()
        return fit


def pixel(surface: cairo.ImageSurface, x: int, y: int) -> tuple[int, int, int]:
    surface.flush()
    data = surface.get_data()
    offset = y * surface.get_stride() + x * 4
    return data[offset + 2], data[offset + 1], data[offset]  # BGRA -> RGB


def close(actual: tuple[int, int, int], expected: tuple[int, int, int]) -> bool:
    return all(abs(a - e) <= 1 for a, e in zip(actual, expected, strict=True))  # cairo rounds colours


def surface_and_context(w: int = 200, h: int = 100) -> tuple[cairo.ImageSurface, cairo.Context]:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    return surface, cairo.Context(surface)


def test_fit_centers_and_hex_rgb() -> None:
    assert render.fit(400, 300, 200, 100) == pytest.approx((1 / 3, 33.33333, 0))
    assert render.hex_rgb("#ff8000") == pytest.approx((1.0, 128 / 255, 0.0))


def test_stage_draws_slide_ink_and_laser() -> None:
    deck, ink = Deck(3), Ink()
    ink.layers[slide_layer(0)] = [Stroke([(100.0, 150.0, 1.0), (300.0, 150.0, 1.0)], COLORS["red"], 20.0)]
    deck.set_laser_on(True)
    deck.set_laser((0.5, 0.2))
    stage = Stage(FakeDoc(), deck, ink)
    surface, cr = surface_and_context()
    stage.draw(cr, 0, 200, 100)
    scale, ox, oy = stage.fit(0, 200, 100)
    assert close(pixel(surface, int(ox + 200 * scale), int(oy + 150 * scale)), (229, 57, 53))  # red ink
    assert close(pixel(surface, int(ox + 200 * scale), int(oy + 60 * scale)), (255, 26, 26))  # laser dot centre
    assert pixel(surface, 5, 50) == (0, 0, 0)  # letterbox


def test_stage_board_uses_board_layer_and_size() -> None:
    deck, ink = Deck(3), Ink()
    deck.toggle_board()
    stage = Stage(FakeDoc(), deck, ink)
    assert stage.layer(1) == "board"
    assert stage.size(1) == render.BOARD_SIZE
    surface, cr = surface_and_context(320, 180)
    stage.draw(cr, 1, 320, 180)
    assert close(pixel(surface, 160, 90), tuple(round(c * 255) for c in BOARD_STYLES["chalk"].bg))  # ty: ignore[invalid-argument-type]


def test_an_area_squeezed_to_nothing_paints_nothing_and_never_breaks_cairo() -> None:
    deck = Deck(3)
    stage = Stage(FakeDoc(), deck, Ink())
    _surface, cr = surface_and_context(10, 10)
    for board in (False, True):
        deck.board = board
        for size in ((0, 0), (0, 50), (50, 0), (-5, 20)):
            scale, _x, _y = stage.draw(cr, 0, *size)
            assert scale > 0
            stage.to_layer(0, *size, 5.0, 5.0)  # pointer events there divide by the scale: must not raise
    assert render.fit(400, 300, 0, 0)[0] > 0
    deck.board = True
    render.draw_board(cr, 0, 0)  # even the board alone survives it


def test_stage_coordinate_conversions() -> None:
    stage = Stage(FakeDoc(), Deck(1), Ink())
    scale, ox, _ = stage.fit(0, 200, 100)
    assert stage.to_layer(0, 200, 100, ox + 40 * scale, 30 * scale) == pytest.approx((40.0, 30.0))
    assert stage.to_fraction(0, 200, 100, ox + 200 * scale, 150 * scale) == pytest.approx((0.5, 0.5))
    assert stage.to_fraction(0, 200, 100, 1.0, 50.0) is None  # in the letterbox


def test_laser_styles_draw_different_shapes() -> None:
    size = (200.0, 100.0)
    spot = (100, 50)
    for look, centre_filled in (("dot", True), ("ring", False), ("cross", True)):
        surface, cr = surface_and_context()
        render.draw_laser(cr, (0.5, 0.5), size, 1.0, LaserStyle(color="#00ff00", size=20.0, style=look, halo=False))
        assert (pixel(surface, *spot) == (0, 255, 0)) is centre_filled, look
    surface, cr = surface_and_context()
    render.draw_laser(cr, (0.5, 0.5), size, 1.0, LaserStyle(size=10.0, halo=True))
    assert pixel(surface, 100 + 15, 50)[0] > 0  # halo extends beyond the dot


def test_highlighter_stroke_is_translucent_and_uniform() -> None:
    surface, cr = surface_and_context(100, 100)
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    # a stroke that crosses itself: a uniform group alpha means the overlap is not darker
    stroke = Stroke([(10.0, 50.0, 1.0), (90.0, 50.0, 1.0), (10.0, 50.0, 1.0)], "#000000", 20.0, 0.5)
    render.draw_strokes(cr, [stroke], 1.0)
    assert 100 < pixel(surface, 50, 50)[0] < 160
    assert pixel(surface, 50, 50) == pixel(surface, 30, 50)


@pytest.mark.parametrize("style", sorted(BOARD_STYLES))
def test_every_board_style_paints_its_background(style: str) -> None:
    surface, cr = surface_and_context(320, 180)
    render.draw_board(cr, 320, 180, style)
    bg = BOARD_STYLES[style].bg
    centre = pixel(surface, 3, 3)
    assert all(abs(a - round(b * 255)) <= 1 for a, b in zip(centre, bg, strict=True))


def test_ruled_board_has_lines() -> None:
    surface, cr = surface_and_context(1600, 900)
    render.draw_board(cr, 1600, 900, "ruled")
    bg_red = round(BOARD_STYLES["ruled"].bg[0] * 255)
    on_a_line = min(pixel(surface, 800, y)[0] for y in range(50, 62))  # a rule sits at y=56
    between = pixel(surface, 800, 84)[0]
    assert on_a_line < bg_red - 15
    assert abs(between - bg_red) <= 1


def test_a_single_point_stroke_is_drawn_as_a_dot() -> None:
    surface, cr = surface_and_context(100, 100)
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    render.draw_strokes(cr, [Stroke([(50.0, 50.0, 1.0)], "#000000", 20.0)], 1.0)
    assert pixel(surface, 50, 50)[0] < 30
    assert pixel(surface, 5, 5) == (255, 255, 255)


def test_zoom_magnifies_around_a_point_and_keeps_input_mapping_exact() -> None:
    deck = Deck(1)
    stage = Stage(FakeDoc(), deck, Ink())
    scale, ox, oy = stage.fit(0, 200, 150)
    assert (scale, ox, oy) == (0.5, 0.0, 0.0)
    deck.set_zoom(2.0, (0.5, 0.5))
    zoomed, zx, zy = stage.fit(0, 200, 150)
    assert (zoomed, zx, zy) == (1.0, -100.0, -75.0)  # the middle of the slide stays in the middle
    assert stage.to_layer(0, 200, 150, 100.0, 75.0) == pytest.approx((200.0, 150.0))
    deck.set_zoom(2.0, (0.0, 0.0))  # a corner cannot be centred: the view stays inside the slide
    assert stage.fit(0, 200, 150) == (1.0, 0.0, 0.0)
    deck.set_zoom(2.0, (1.0, 1.0))
    assert stage.fit(0, 200, 150) == (1.0, -200.0, -150.0)


def test_zoom_draws_the_magnified_slide_with_constant_pen_and_laser_size() -> None:
    deck, ink = Deck(1), Ink()
    ink.layers[slide_layer(0)] = [Stroke([(300.0, 150.0, 1.0), (301.0, 150.0, 1.0)], COLORS["red"], 20.0)]
    deck.set_laser_on(True)
    deck.set_laser((0.5, 0.5))
    deck.set_zoom(2.0, (0.5, 0.5))
    stage = Stage(FakeDoc(), deck, ink)
    surface, cr = surface_and_context()
    assert stage.draw(cr, 0, 200, 100) == stage.fit(0, 200, 100)
    assert close(pixel(surface, 100, 50), (255, 26, 26))  # the laser sits in the middle: it is what is magnified
    assert pixel(surface, 199, 99) == (255, 255, 255)  # the slide fills the screen: no letterbox


def test_zoom_wider_than_the_content_centres_it() -> None:
    deck = Deck(1)
    stage = Stage(FakeDoc(), deck, Ink())
    deck.set_zoom(1.2, (0.0, 0.5))
    scale, ox, _ = stage.fit(0, 800, 100)  # the slide is narrower than the window even magnified: centred
    assert ox + scale * PAGE_W / 2 == pytest.approx(400.0)
