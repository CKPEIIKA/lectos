import pytest

from lectos.deck import Deck, Timer, format_seconds

PAGES = 10
LAST = PAGES - 1


def test_goto_clamps_and_projects() -> None:
    deck = Deck(PAGES)
    deck.goto(99)
    assert (deck.view, deck.page) == (LAST, LAST)
    deck.step(-99)
    assert (deck.view, deck.page) == (0, 0)


def test_freeze_holds_projector_and_unfreeze_catches_up() -> None:
    deck = Deck(PAGES)
    deck.goto(2)
    deck.set_frozen(True)
    deck.goto(5)
    assert (deck.view, deck.page) == (5, 2)
    deck.set_frozen(False)
    assert deck.page == 5


def test_peek_never_moves_projector() -> None:
    deck = Deck(PAGES)
    deck.peek(7)
    assert (deck.view, deck.page) == (7, 0)


def test_set_pages_clamps_and_roundtrip() -> None:
    deck = Deck(PAGES)
    deck.goto(LAST)
    deck.set_pages(3)
    assert (deck.view, deck.page) == (2, 2)
    other = Deck(PAGES)
    other.load({"page": 4, "view": 6, "frozen": True})
    assert (other.page, other.view, other.frozen) == (4, 6, True)
    other.load({"page": "x", "frozen": 1})  # malformed input is ignored


def test_subscribers_called() -> None:
    deck = Deck(PAGES)
    calls: list[int] = []
    deck.subscribe(lambda: calls.append(1))
    deck.goto(1)
    deck.toggle_blackout()
    assert len(calls) == 2


def test_timer_pause_resume_and_estimates() -> None:
    timer = Timer(target_min=1)
    timer.toggle(100.0)
    assert timer.elapsed(110.0) == 10.0
    timer.toggle(110.0)
    assert timer.elapsed(500.0) == 10.0
    assert timer.left(500.0) == 50.0
    timer.toggle(500.0)
    assert timer.pace_left(510.0, 2, 10) == pytest.approx(20.0 / 2 * 8)
    assert timer.pace_left(510.0, 0, 10) is None


def test_timer_roundtrip_keeps_counting_across_restart() -> None:
    timer = Timer()
    timer.toggle(100.0)
    restored = Timer()
    restored.load(timer.to_dict())
    assert restored.elapsed(160.0) == 60.0
    restored.load({"base": "bad"})  # ignored
    assert restored.elapsed(160.0) == 60.0


def test_format_seconds() -> None:
    assert format_seconds(65) == "1:05"
    assert format_seconds(3725) == "1:02:05"
    assert format_seconds(-30) == "-0:30"


def test_board_and_laser_state() -> None:
    deck = Deck(PAGES)
    deck.set_laser((0.5, 0.5))
    assert deck.laser is None  # ignored while the laser is off
    deck.set_laser_on(True)
    deck.set_laser((0.25, 0.75))
    assert deck.laser == (0.25, 0.75)
    deck.set_laser(None)
    deck.set_laser((0.1, 0.1))
    deck.set_laser_on(False)
    assert deck.laser is None
    deck.toggle_board()
    assert deck.to_dict()["board"] is True
    other = Deck(PAGES)
    other.load(deck.to_dict())
    assert other.board is True


def test_board_style_is_validated_and_saved() -> None:
    deck = Deck(PAGES)
    assert deck.set_board_style("grid") is True
    assert deck.set_board_style("rainbow") is False
    assert deck.board_style == "grid"
    other = Deck(PAGES)
    other.load(deck.to_dict())
    assert other.board_style == "grid"
    other.load({"board_style": "nope"})
    assert other.board_style == "grid"
    calls: list[int] = []
    deck.subscribe(lambda: calls.append(1))
    deck.touch()
    assert calls == [1]


@pytest.mark.parametrize(
    ("text", "minutes"),
    [
        ("90", 90), ("45m", 45), ("2h", 120), ("1h30", 90), ("1h30m", 90), ("1:30", 90), ("0:45", 45),
        (" 1 h 15 ", 75), ("75", 75), ("24h", 1440), ("23:59", 1439),
    ],
)  # fmt: skip
def test_parse_minutes_accepts_lecture_lengths(text: str, minutes: int) -> None:
    from lectos.deck import parse_minutes

    assert parse_minutes(text) == minutes


@pytest.mark.parametrize("text", ["", "0", "0:00", "1441", "25h", "abc", "1:75", "1h75", "h", "1h1h", "-5", "1.5"])
def test_parse_minutes_rejects_bad_lengths(text: str) -> None:
    from lectos.deck import parse_minutes

    assert parse_minutes(text) is None


def test_schedule_delta_is_on_time_inside_the_current_slides_share() -> None:
    timer = Timer(target_min=10)  # 10 slides: one minute each
    assert timer.schedule_delta(0.0, 0, PAGES) is None  # not started
    timer.toggle(1000.0)
    assert timer.schedule_delta(1030.0, 0, PAGES) == 0.0  # 30 s into slide 1: on time
    assert timer.schedule_delta(1000.0 + 90, 1, PAGES) == 0.0  # 90 s, on slide 2 (60..120 s)
    assert timer.schedule_delta(1000.0 + 20, 3, PAGES) == 160.0  # reached slide 4 (starts at 180 s) after 20 s
    assert timer.schedule_delta(1000.0 + 400, 2, PAGES) == -220.0  # still on slide 3 (ends at 180 s) after 400 s
    assert timer.schedule_delta(1000.0 + 5, 0, 0) is None


def test_finish_at_uses_pace_when_known_else_the_plan() -> None:
    timer = Timer(target_min=10)
    assert timer.finish_at(1000.0, 0, PAGES) == 1000.0 + 600.0  # not started: planned remaining
    timer.toggle(1000.0)
    # after 100 s on slide 2 of 10: pace 50 s/slide, 8 slides left -> 400 s
    assert timer.finish_at(1100.0, 1, PAGES) == pytest.approx(1100.0 + 400.0)


def test_schedule_summary_text(monkeypatch: pytest.MonkeyPatch) -> None:
    from lectos import deck as deck_module
    from lectos.deck import schedule_summary

    monkeypatch.setattr(deck_module.time, "localtime", lambda t: __import__("time").gmtime(t))
    timer = Timer(target_min=10)
    text = schedule_summary(timer, 0.0, 0, PAGES)
    assert text == "ends 00:10  00:00"  # nothing measured yet: no ahead/behind part
    timer.toggle(1000.0)
    assert schedule_summary(timer, 1000.0 + 20, 3, PAGES).startswith("ahead 2:40  ends ")
    assert schedule_summary(timer, 1000.0 + 400, 2, PAGES).startswith("behind 3:40  ends ")
    assert schedule_summary(timer, 1000.0 + 30, 0, PAGES).startswith("on time  ends ")
    assert "·" not in schedule_summary(timer, 1000.0 + 30, 0, PAGES)
