from lectos.keys import Action, Vim


def feed(vim: Vim, keys: str) -> list[Action | None]:
    return [vim.feed(k) for k in keys]


def test_counts_and_commands() -> None:
    vim = Vim()
    assert feed(vim, "12l")[-1] == Action("next", 12)
    assert vim.feed("h") == Action("prev", None)


def test_gg_and_G() -> None:
    vim = Vim()
    assert feed(vim, "gg")[-1] == Action("goto", 1)
    assert feed(vim, "7G")[-1] == Action("goto", 7)
    assert vim.feed("G") == Action("last")
    assert feed(vim, "5gg")[-1] == Action("goto", 5)


def test_unknown_key_resets_and_is_not_consumed() -> None:
    vim = Vim()
    assert feed(vim, "3x")[-1] is None
    assert vim.feed("l") == Action("next", None)


def test_zero_alone_is_not_a_count() -> None:
    assert Vim().feed("0") is None
