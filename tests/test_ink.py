import json

from lectos.ink import BOARD_LAYER, COLORS, MAX_STROKES_PER_LAYER, Ink, slide_layer

LAYER = slide_layer(2)


def draw(ink: Ink, layer: str, *points: tuple[float, float]) -> None:
    ink.begin(layer, *points[0], 0.5)
    for x, y in points[1:]:
        ink.extend(layer, x, y, 0.5)


def test_strokes_use_current_tool_and_layers_are_separate() -> None:
    ink = Ink()
    ink.tool.color, ink.tool.width = COLORS["red"], 7.0
    draw(ink, LAYER, (0, 0), (10, 10))
    draw(ink, BOARD_LAYER, (5, 5), (6, 6))
    assert [(s.color, s.width, len(s.points)) for s in ink.strokes(LAYER)] == [(COLORS["red"], 7.0, 2)]
    assert len(ink.strokes(BOARD_LAYER)) == 1
    assert ink.strokes(slide_layer(0)) == []
    assert ink.dirty


def test_extend_drops_points_that_barely_move() -> None:
    ink = Ink()
    draw(ink, LAYER, (0, 0), (0.1, 0.1), (0.2, 0.0), (5, 5))
    assert len(ink.strokes(LAYER)[0].points) == 2


def test_undo_redo_and_clear_are_undoable() -> None:
    ink = Ink()
    draw(ink, LAYER, (0, 0), (9, 9))
    draw(ink, LAYER, (20, 20), (30, 30))
    ink.undo(LAYER)
    assert len(ink.strokes(LAYER)) == 1
    ink.redo(LAYER)
    assert len(ink.strokes(LAYER)) == 2
    ink.clear(LAYER)
    assert ink.strokes(LAYER) == []
    ink.undo(LAYER)
    assert len(ink.strokes(LAYER)) == 2
    ink.undo(slide_layer(9))  # nothing to undo is fine


def test_new_stroke_after_undo_discards_redo() -> None:
    ink = Ink()
    draw(ink, LAYER, (0, 0), (9, 9))
    ink.undo(LAYER)
    draw(ink, LAYER, (1, 1), (8, 8))
    ink.redo(LAYER)
    assert len(ink.strokes(LAYER)) == 1


def test_eraser_removes_touched_strokes_as_one_undo_step() -> None:
    ink = Ink()
    draw(ink, LAYER, (0, 0), (10, 0))
    draw(ink, LAYER, (100, 100), (110, 100))
    ink.erase_begin(LAYER)
    ink.erase_at(LAYER, 5, 0)
    ink.erase_at(LAYER, 105, 100)
    ink.erase_end(LAYER)
    assert ink.strokes(LAYER) == []
    ink.undo(LAYER)
    assert len(ink.strokes(LAYER)) == 2


def test_erase_gesture_that_hits_nothing_leaves_no_undo_step() -> None:
    ink = Ink()
    draw(ink, LAYER, (0, 0), (10, 0))
    ink.erase_begin(LAYER)
    ink.erase_at(LAYER, 500, 500)
    ink.erase_end(LAYER)
    ink.undo(LAYER)  # undoes the stroke, not a phantom erase
    assert ink.strokes(LAYER) == []


def test_layer_is_capped() -> None:
    ink = Ink()
    for i in range(MAX_STROKES_PER_LAYER + 5):
        ink.begin(LAYER, float(i), 0.0, 1.0)
    assert len(ink.strokes(LAYER)) == MAX_STROKES_PER_LAYER


def test_roundtrip_through_json_and_dirty_reset() -> None:
    ink = Ink()
    ink.tool.color = COLORS["blue"]
    draw(ink, LAYER, (0.123, 4.567), (10.04, 20.06))
    draw(ink, BOARD_LAYER, (1, 2), (3, 4))
    other = Ink()
    other.load(json.loads(json.dumps(ink.to_dict())))
    assert other.dirty is False
    assert other.strokes(LAYER)[0].color == COLORS["blue"]
    assert other.strokes(LAYER)[0].points[0] == (0.1, 4.6, 0.5)
    assert len(other.strokes(BOARD_LAYER)) == 1


def test_load_skips_malformed_data() -> None:
    ink = Ink()
    ink.load(
        {
            "layers": {
                "s1": [
                    {"c": "#fff000", "w": 3, "p": [[1, 2, 0.5]]},
                    {"c": "red", "w": 3, "p": [[1, 2, 0.5]]},  # bad colour
                    {"c": "#zzzzzz", "w": 3, "p": [[1, 2, 0.5]]},  # '#' but not hex: would crash rendering
                    {"c": "#abc", "w": 3, "p": [[1, 2, 0.5]]},  # too short
                    {"c": "#", "w": 3, "p": [[1, 2, 0.5]]},
                    {"c": "#fff000", "w": "x", "p": [[1, 2, 0.5]]},  # bad width
                    {"c": "#fff000", "w": 3, "p": [[1, 2]]},  # bad point
                    "junk",
                ],
                "s2": "junk",
            }
        }
    )
    assert list(ink.layers) == ["s1"]
    assert len(ink.layers["s1"]) == 1
    ink.load("not a dict")
    assert ink.layers == {}


def test_subscribers_see_changes() -> None:
    ink = Ink()
    calls: list[int] = []
    ink.subscribe(lambda: calls.append(1))
    draw(ink, LAYER, (0, 0), (9, 9))
    ink.notify()
    assert len(calls) == 3


def test_highlighter_makes_wide_translucent_strokes() -> None:
    ink = Ink()
    ink.tool.width, ink.tool.highlighter, ink.tool.highlight_alpha = 5.0, True, 0.25
    draw(ink, LAYER, (0, 0), (10, 10))
    stroke = ink.strokes(LAYER)[0]
    assert (stroke.width, stroke.alpha) == (15.0, 0.25)
    other = Ink()
    other.load(json.loads(json.dumps(ink.to_dict())))
    assert other.strokes(LAYER)[0].alpha == 0.25


def test_smoothing_keeps_endpoints_and_reduces_jitter() -> None:
    ink = Ink()
    ink.tool.smoothing = 2
    ink.begin(LAYER, 0.0, 0.0, 1.0)
    for i, y in enumerate([4.0, -4.0, 4.0, -4.0, 4.0, -4.0], start=1):
        ink.extend(LAYER, i * 10.0, y, 1.0)
    before = [p[1] for p in ink.strokes(LAYER)[0].points]
    ink.finish(LAYER)
    after = [p[1] for p in ink.strokes(LAYER)[0].points]
    assert len(after) == len(before)
    assert (after[0], after[-1]) == (before[0], before[-1])
    assert max(abs(y) for y in after[1:-1]) < max(abs(y) for y in before[1:-1])
    ink.tool.smoothing = 0
    draw(ink, LAYER, (0, 0), (50, 50), (100, 0))
    ink.finish(LAYER)
    assert ink.strokes(LAYER)[-1].points[1][:2] == (50.0, 50.0)


def test_eraser_radius_comes_from_the_tool() -> None:
    ink = Ink()
    draw(ink, LAYER, (0, 0), (10, 0))
    ink.tool.eraser_radius = 5.0
    ink.erase_at(LAYER, 0.0, 20.0)
    assert len(ink.strokes(LAYER)) == 1
    ink.tool.eraser_radius = 25.0
    ink.erase_at(LAYER, 0.0, 20.0)
    assert ink.strokes(LAYER) == []


def test_clear_all_empties_every_layer_and_each_can_be_undone() -> None:
    ink = Ink()
    draw(ink, LAYER, (0, 0), (9, 9))
    draw(ink, slide_layer(5), (0, 0), (9, 9))
    draw(ink, BOARD_LAYER, (0, 0), (9, 9))
    assert ink.clear_all() == 3
    assert all(not ink.strokes(name) for name in (LAYER, slide_layer(5), BOARD_LAYER))
    assert ink.clear_all() == 0
    ink.undo(BOARD_LAYER)
    assert len(ink.strokes(BOARD_LAYER)) == 1
    assert ink.strokes(LAYER) == []  # only that layer came back


def test_parse_number_and_smooth_edge_cases() -> None:
    from lectos.ink import parse_number, smooth

    assert parse_number("0.5", 0.1, 0.9) == 0.5
    assert parse_number("2", 0.1, 0.9) is None
    assert parse_number("abc", 0.1, 0.9) is None
    pts = [(0.0, 0.0, 1.0), (1.0, 1.0, 1.0)]
    assert smooth(pts, 3) == pts
    assert smooth(pts * 3, 0) == pts * 3


def test_restore_cleared_is_forgotten_once_the_layer_changes_again() -> None:
    ink = Ink()
    draw(ink, LAYER, (0, 0), (9, 9))  # stroke A
    ink.clear_all()
    draw(ink, LAYER, (50, 50), (60, 60))  # the presenter draws stroke B before restoring
    assert ink.restore_cleared() == 0  # must not undo B and then claim A came back
    assert len(ink.strokes(LAYER)) == 1
    assert ink.strokes(LAYER)[0].points[0][:2] == (50.0, 50.0)  # B is still there


def test_restore_cleared_after_an_explicit_undo_does_not_undo_twice() -> None:
    ink = Ink()
    draw(ink, LAYER, (0, 0), (9, 9))
    draw(ink, BOARD_LAYER, (0, 0), (9, 9))
    ink.clear_all()
    ink.undo(LAYER)  # the presenter already got this layer back by hand
    assert ink.restore_cleared() == 1  # only the board is still pending
    assert len(ink.strokes(LAYER)) == 1
    assert len(ink.strokes(BOARD_LAYER)) == 1


def test_load_forgets_pending_restore() -> None:
    ink = Ink()
    draw(ink, LAYER, (0, 0), (9, 9))
    ink.clear_all()
    ink.load({"layers": {}})
    assert ink.restore_cleared() == 0
