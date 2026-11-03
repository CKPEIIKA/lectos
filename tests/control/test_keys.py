
from lectos.control.keys import Action, Vim, check_binding


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
    assert feed(vim, "3y")[-1] is None
    assert vim.feed("l") == Action("next", None)


def test_zero_alone_is_not_a_count() -> None:
    assert Vim().feed("0") is None


def test_bindings_add_change_and_free_keys() -> None:
    vim = Vim({"x": "color red", "l": "last", "h": ""})
    assert vim.feed("x") == Action("color", None, "red")
    assert Action("color", None, "red").line == "color red"
    assert vim.feed("l") == Action("last")
    assert vim.feed("h") is None  # freed by the configuration
    assert Action("next", 3).line == "next 3"
    assert Action("next").line == "next"
    assert vim.key_for("last") == "l"
    assert vim.key_for("nothing") == ""


def test_bind_and_unbind_report_and_remember() -> None:
    vim = Vim()
    known = {"color", "next"}
    assert "runs color red" in vim.rebind("y color red", known)
    assert vim.feed("y") == Action("color", None, "red")
    assert vim.changed == {"y": "color red"}
    assert "is free" in vim.unbind("y extra words", known)
    assert vim.feed("y") is None
    assert vim.rebind("", known).startswith("bind KEY")
    assert vim.unbind("", known).startswith("bind KEY")
    assert "unknown command" in vim.rebind("y nonsense", known)
    assert "one printable character" in vim.rebind("yy next", known)
    assert "counts" in vim.rebind("5 next", known)
    assert "counts" in vim.rebind("g next", known)
    assert check_binding(":", "command-line", known) is None
    assert check_binding(" ", "next", known) is not None


def test_restore_applies_valid_remembered_keys_only() -> None:
    vim = Vim()
    vim.restore({"y": "next 2", "z": "nonsense", "9": "next", 5: "next", "w": 3}, {"next"})
    assert vim.bindings["y"] == "next 2"
    assert vim.changed == {"y": "next 2"}
    assert "w" not in vim.bindings
    vim.restore("not a table", {"next"})
