from lectos.model import layout


def test_fixed_modes_ignore_width() -> None:
    assert layout.resolve("compact", 3000) == "compact"
    assert layout.resolve("wide", 500) == "wide"


def test_auto_has_hysteresis() -> None:
    assert layout.resolve("auto", 1000) == "compact"
    assert layout.resolve("auto", 1920) == "wide"
    assert layout.resolve("auto", 1450, "compact") == "compact"  # between thresholds: stay
    assert layout.resolve("auto", 1450, "wide") == "wide"
    assert layout.resolve("auto", 1300, "wide") == "compact"


def test_strip_pages_clip_to_deck() -> None:
    assert layout.strip_pages(5, 20, 3, 8) == list(range(2, 14))
    assert layout.strip_pages(0, 20, 3, 8) == list(range(0, 9))
    assert layout.strip_pages(19, 20, 3, 8) == [16, 17, 18, 19]
    assert layout.strip_pages(2, 3, 3, 16) == [0, 1, 2]
    assert layout.strip_pages(4, 10, 0, 0) == [4]


def test_thumb_width_fits_and_is_bounded() -> None:
    assert layout.thumb_width(1900, 12) * 12 + 6 * 13 <= 1900
    assert layout.thumb_width(300, 12) == layout.MIN_THUMB_PX
    assert layout.thumb_width(5000, 3) == layout.MAX_THUMB_PX
    assert layout.thumb_width(1000, 0) == layout.MAX_THUMB_PX


def test_clamp_count() -> None:
    assert layout.clamp_count(99, layout.MAX_UPCOMING) == layout.MAX_UPCOMING
    assert layout.clamp_count(-2, layout.MAX_UPCOMING) == 0
