from lectos.notes import Span, parse


def test_parse_headings_emphasis_bullets() -> None:
    spans = parse("# Title\nsome **bold** and *it* and `c`\n- item\n")
    assert Span("Title\n", "h1") in spans
    assert Span("bold", "bold") in spans
    assert Span("it", "italic") in spans
    assert Span("c", "code") in spans
    assert any("• item" in s.text for s in spans)


def test_parse_math_variants() -> None:
    spans = parse("inline $a^2$ and $$\nx=1\n$$ and \\[y=2\\] cost $5 and $6")
    assert [(s.text, s.style) for s in spans if s.style in ("math", "display")] == [
        ("a^2", "math"),
        ("x=1", "display"),
        ("y=2", "display"),
    ]


def test_math_not_formatted_as_emphasis() -> None:
    spans = parse("$a*b*c$")
    assert spans == [Span("a*b*c", "math")]
