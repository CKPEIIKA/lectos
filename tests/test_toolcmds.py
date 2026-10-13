import pytest

from lectos.deck import Deck
from lectos.ink import Ink
from lectos.style import LaserStyle
from lectos.toolcmds import Tools


@pytest.fixture
def tools() -> Tools:
    return Tools(Ink(), Deck(3), LaserStyle())


def test_pen_settings_and_messages(tools: Tools) -> None:
    assert tools.color("blue") == "pen colour #1e88e5"
    assert tools.ink.tool.color == "#1e88e5"
    assert tools.color("nope").startswith("colour:")
    assert tools.width("12") == "pen width 12"
    assert tools.width("99").startswith("width needs")
    assert tools.highlighter(True) == "highlighter on"
    assert tools.ink.tool.highlighter is True
    assert tools.highlighter(False) == "pen"
    assert tools.smoothing("3") == "smoothing 3"
    assert tools.smoothing("9").startswith("smooth needs")
    assert tools.smoothing("1.5").startswith("smooth needs")
    assert tools.eraser_size("30") == "eraser radius 30"
    assert tools.eraser_size("1").startswith("eraser-size needs")
    assert tools.highlight_alpha("0.5") == "highlighter opacity 0.5"
    assert tools.highlight_alpha("5").startswith("highlight-alpha needs")
    assert (tools.ink.tool.smoothing, tools.ink.tool.eraser_radius, tools.ink.tool.highlight_alpha) == (3, 30.0, 0.5)


def test_board_and_laser_settings_notify_subscribers(tools: Tools) -> None:
    calls: list[int] = []
    tools.deck.subscribe(lambda: calls.append(1))
    assert tools.board_style("grid") == "board background grid"
    assert tools.board_style("rainbow").startswith("board-style:")
    assert tools.laser_color("#00ff00") == "laser colour #00ff00"
    assert tools.laser_size("14") == "laser size 14"
    assert tools.laser_size("100").startswith("laser-size needs")
    assert tools.laser_style("ring") == "laser shape ring"
    assert tools.laser_style("star").startswith("laser-style:")
    assert (tools.laser.color, tools.laser.size, tools.laser.style) == ("#00ff00", 14.0, "ring")
    assert len(calls) == 4  # board style + three laser changes redraw the views


def test_clear_all_reports_what_it_did(tools: Tools) -> None:
    assert tools.clear_all() == "nothing to erase"
    tools.ink.begin("s0", 0.0, 0.0, 1.0)
    tools.ink.begin("board", 0.0, 0.0, 1.0)
    assert "erased 2 strokes" in tools.clear_all()
