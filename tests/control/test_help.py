from lectos.control import commands, keys


def key_for(name: str) -> str:
    return keys.key_for(name)


def test_every_key_binding_has_help_except_the_command_line_prompt() -> None:
    bound = set(keys.ACTIONS.values()) - {"command-line"}
    assert bound <= set(commands.HELP)


def test_help_entries_are_grouped_and_complete() -> None:
    entries = commands.help_entries(["goto", "freeze", "laser", "nonexistent", "next"], key_for)
    groups = [group for group, *_ in entries]
    assert groups == sorted(groups, key=commands.GROUPS.index)
    usages = [usage for _, usage, _, _ in entries]
    assert usages == ["goto N", "next [N]", "freeze [on|off]", "laser [on|off]"]
    assert dict((u, k) for _, u, _, k in entries)["next [N]"] == "l"


def test_every_help_entry_is_well_formed() -> None:
    for name, entry in commands.HELP.items():
        assert entry.group in commands.GROUPS, name
        assert entry.usage.split()[0] == name, name
        assert entry.text.endswith((".", ")")) or entry.text[-1].isalnum(), name


def test_describe() -> None:
    assert "Go to slide N" in commands.describe("goto", key_for)
    assert "[key l]" in commands.describe("next", key_for)
    assert "no such command" in commands.describe("zzz", key_for)
