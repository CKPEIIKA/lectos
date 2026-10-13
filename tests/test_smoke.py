from lectos.cli import build_parser
from lectos.notes import split_markdown


def test_parser_defaults() -> None:
    args = build_parser("lectos").parse_args(["slides.pdf"])
    assert args.notes is None
    assert args.windowed is False


def test_split_markdown_assigns_slides() -> None:
    text = "intro\n<!-- slide: 2 -->\n## A\n<!-- slide: 3 -->\nB\n"
    assert split_markdown(text) == [(None, "intro\n"), (2, "\n## A\n"), (3, "\nB\n")]
