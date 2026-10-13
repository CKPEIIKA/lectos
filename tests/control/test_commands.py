from lectos.control import commands

NAMES = ["blackout", "first", "freeze", "fullscreen", "projector-fullscreen", "search", "show-slide"]


def test_parse_numbers_marks_and_arguments() -> None:
    assert commands.parse(":12") == ("goto", "12")
    assert commands.parse(":$") == ("last", "")
    assert commands.parse(":search carbuncle instability ") == ("search", "carbuncle instability")
    assert commands.parse("freeze") == ("freeze", "")


def test_flag_and_count() -> None:
    assert commands.flag("on", False) is True
    assert commands.flag("off", True) is False
    assert commands.flag("", True) is False
    assert commands.flag("", False) is True
    assert commands.count("5") == 5
    assert commands.count("") == 1
    assert commands.count("x") == 1


def test_complete_unique_extends_and_lists() -> None:
    assert commands.complete(":sea", NAMES) == (":search ", ["search"])
    assert commands.complete(":fr", NAMES) == (":freeze ", ["freeze"])
    line, matches = commands.complete(":f", NAMES)
    assert (line, matches) == (":f", ["first", "freeze", "fullscreen"])
    assert commands.complete(":fu", NAMES) == (":fullscreen ", ["fullscreen"])
    assert commands.complete(":s", NAMES)[1] == ["search", "show-slide"]
    assert commands.complete(":", NAMES)[0] == ":"


def test_complete_shared_prefix_and_no_match() -> None:
    assert commands.complete(":p", NAMES) == (":projector-fullscreen ", ["projector-fullscreen"])
    assert commands.complete(":zzz", NAMES) == (":zzz", [])
    assert commands.complete(":search foo", NAMES) == (":search foo", [])  # arguments are left alone
