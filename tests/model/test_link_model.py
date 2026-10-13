from lectos.model.links import Link, hit, is_safe


def test_a_link_contains_its_rectangle_including_the_edges() -> None:
    link = Link(10, 20, 30, 40, page=2)
    assert link.contains(10, 20)
    assert link.contains(40, 60)
    assert not link.contains(9.9, 30)
    assert not link.contains(20, 60.1)


def test_where_links_overlap_the_last_one_wins() -> None:
    below, above = Link(0, 0, 100, 100, page=1), Link(40, 40, 20, 20, uri="https://example.org")
    assert hit([below, above], 50, 50) is above
    assert hit([below, above], 10, 10) is below
    assert hit([below, above], 200, 10) is None
    assert hit([], 1, 1) is None


def test_only_web_and_mail_addresses_are_safe_to_open() -> None:
    assert all(is_safe(u) for u in ("http://a.b", "HTTPS://a.b/c?d=1", "mailto:me@example.org"))
    assert not any(is_safe(u) for u in ("file:///etc/passwd", "javascript:alert(1)", "/usr/bin/x", "ftp://a.b", ""))
