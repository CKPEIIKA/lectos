from lectos.model import header


def test_items_are_consistent() -> None:
    assert set(header.ITEMS) | set(header.SPECIAL) == set(header.ITEM_NAMES)
    assert set(header.DEFAULT_START) | set(header.DEFAULT_END) <= set(header.ITEM_NAMES)
    for name, item in header.ITEMS.items():
        assert item.icons, name
        assert all(icon.endswith("-symbolic") for icon in item.icons), name
        assert item.label and item.command and item.tip, name


def test_toggle_items_name_a_command_that_takes_on_off() -> None:
    toggles = {name for name, item in header.ITEMS.items() if item.toggle}
    assert toggles == {"freeze", "blackout", "board", "laser", "draw", "eraser", "highlighter", "sketch"}
