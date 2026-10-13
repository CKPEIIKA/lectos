from collections.abc import Callable

from lectos.deck import Deck
from lectos.projection import GTK_CAPS, NullProjector, ProjectorSync, apply_caps, gated


class Recorder(NullProjector):
    def __init__(self) -> None:
        self.pages: list[int] = []

    def goto(self, page: int) -> None:
        self.pages.append(page)


def test_sync_sends_only_changes_and_force_resends() -> None:
    deck, proj = Deck(5), Recorder()
    sync = ProjectorSync(deck, proj, lambda _m: None)
    deck.goto(0)  # unchanged from the initial page: still counts as the first send
    deck.goto(0)
    deck.goto(2)
    deck.peek(4)  # view only
    assert proj.pages == [0, 2]
    sync.force()
    assert proj.pages == [0, 2, 2]


def test_sync_reports_errors_instead_of_raising() -> None:
    class Broken(NullProjector):
        def goto(self, page: int) -> None:
            raise RuntimeError("gone")

    messages: list[str] = []
    deck = Deck(3)
    ProjectorSync(deck, Broken(), messages.append)
    deck.goto(1)
    assert messages == ["projector: gone"]


def test_gated_and_apply_caps() -> None:
    said: list[str] = []
    calls: list[str] = []
    table: dict[str, Callable[[str], None]] = {
        "board": lambda a: calls.append(f"board {a}"),
        "next": lambda a: calls.append("next"),
        "undo": lambda a: calls.append("undo"),
    }
    apply_caps(table, frozenset({"board"}), said.append)
    table["board"]("on")
    table["undo"]("")
    table["next"]("")
    assert calls == ["board on", "next"]
    assert said == ["undo: not supported by this projector"]
    assert gated(lambda a: None, "ink", GTK_CAPS, said.append, "x") is not None
