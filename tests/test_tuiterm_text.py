import pytest

from lectos.notes import parse
from lectos.tuiterm import KeyDecoder, decode
from lectos.tuitext import clip, pad, visible_len, wrap
from lectos.unimath import to_unicode


def test_decode_keys() -> None:
    assert decode(b"l5G:/") == ["l", "5", "G", ":", "/"]
    assert decode(b"\x1b[A\x1b[B\x1b[C\x1b[D\x1bOA") == ["Up", "Down", "Right", "Left", "Up"]
    assert decode(b"\x1b[5~\x1b[6~\x1b[H\x1b[F\x1b[Z") == ["PageUp", "PageDown", "Home", "End", "BackTab"]
    assert decode(b"\r\t\x7f\x03\x1b") == ["Enter", "Tab", "Backspace", "C-c", "Esc"]
    assert decode("\u0430".encode()) == ["\u0430"]
    assert decode(b"\x1b[99~") == []  # unknown sequences are dropped


def test_clip_and_pad_ignore_escape_sequences() -> None:
    styled = "\x1b[1mhello world\x1b[0m"
    assert visible_len(styled) == 11
    assert visible_len(clip(styled, 5)) == 5
    assert visible_len(pad("ab", 6)) == 6
    assert visible_len(pad(styled, 4)) == 4


def test_wrap_respects_width_and_styles_headings_and_math() -> None:
    lines = wrap(
        parse("# Title\nSome **bold** text with math $a^2$ and a long tail that must wrap\n\n$$\\frac{a}{b}$$\n- item"),
        24,
    )
    assert all(visible_len(line) <= 24 for line in lines)
    assert "\x1b[1;4mTitle" in lines[0]
    assert any("a/b" in line for line in lines)
    assert any("a²" in line for line in lines)
    assert "" in lines  # blank lines survive, but never trail
    assert lines[-1] == "• item"
    assert wrap([], 10) == []


@pytest.mark.parametrize(
    ("tex", "expected"),
    [
        (r"\partial_t U + \nabla\cdot F(U) = S(U)", "∂ₜ U + ∇· F(U) = S(U)"),
        (r"a^2+b^2=c^2", "a²+b²=c²"),
        (
            r"\hat F = \frac{F_L+F_R}{2} - \frac12 \lvert\tilde A\rvert\,(U_R-U_L)",
            "F\u0302 = (F_L+F_R)/2 - 1/2 |A\u0303| (U_R-U_L)",
        ),
        (r"\frac{\partial\mathbf U}{\partial t}", "(∂U)/(∂ t)"),
        (r"x_{ij}^{n+1} \to \sqrt{x^2+y^2}", "x_(ij)ⁿ⁺¹ → √(x²+y²)"),
        (r"\alpha_1 \leq \beta \unknownmacro", r"α₁ ≤ β \unknownmacro"),
    ],
)
def test_unicode_math(tex: str, expected: str) -> None:
    assert to_unicode(tex) == expected


def test_key_decoder_keeps_a_utf8_character_split_across_reads() -> None:
    data = "привет".encode()
    for cut in range(1, len(data)):
        decoder = KeyDecoder()
        assert decoder.feed(data[:cut]) + decoder.feed(data[cut:]) == list("привет"), cut
    decoder = KeyDecoder()
    assert decoder.feed(b"\xd0") == []  # half a character: nothing yet, nothing lost
    assert decoder.feed(b"\xbf") == ["\u043f"]
    assert decoder.feed(b"\x1b[A l") == ["Up", " ", "l"]


def test_one_shot_decode_still_drops_garbage() -> None:
    assert decode(b"\xff\xfel") == ["l"]
