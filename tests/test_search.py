from lectos.search import MAX_HITS, find


def test_find_matches_notes_and_slides_case_insensitively() -> None:
    notes = [(None, "intro"), (2, "The Carbuncle   instability appears")]
    slides = ["title", "carbuncle instability\nin shocks"]
    hits = find("carbuncle INSTABILITY", slides, notes)
    assert [(h.kind, h.index, h.slide) for h in hits] == [("notes", 1, 2), ("slide", 1, 2)]
    assert "Carbuncle instability" in hits[0].snippet
    assert find("carbuncle instability", ["carbuncle\n   instability"], [])[0].index == 0


def test_find_empty_query_and_cap() -> None:
    assert find("  ", ["a"], []) == []
    assert len(find("a", ["a" * 500], [])) == MAX_HITS
