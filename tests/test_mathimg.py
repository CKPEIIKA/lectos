import shutil
from pathlib import Path

import pytest

from lectos import mathimg

pytestmark = pytest.mark.skipif(not (shutil.which("latex") and shutil.which("dvipng")), reason="needs latex and dvipng")

PNG_MAGIC = b"\x89PNG"


@pytest.mark.integration
def test_render_batches_and_isolates_bad_formula(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    good = mathimg.Formula(r"\frac{\partial U}{\partial t}=0", True)
    bad = mathimg.Formula(r"\undefinedmacro{", False)
    inline = mathimg.Formula("a^2", False)
    out = mathimg.render([good, bad, inline])
    assert set(out) == {good, inline}
    assert out[good].read_bytes().startswith(PNG_MAGIC)
    assert mathimg.render([good]) == {good: out[good]}  # served from cache


@pytest.mark.integration
def test_formulas_are_drawn_in_the_requested_colour_and_cached_per_colour(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import cairo

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    formula = mathimg.Formula("x^2+y^2", False)
    dark_text = mathimg.render([formula], fg="#000000")[formula]
    light_text = mathimg.render([formula], fg="#ffffff")[formula]
    assert dark_text != light_text  # separate cache files per colour

    def brightest_ink(path: Path) -> int:
        surface = cairo.ImageSurface.create_from_png(str(path))
        data = surface.get_data()
        stride = surface.get_stride()
        values = [
            data[y * stride + x * 4 + 2]  # red channel of pixels that have any ink
            for y in range(surface.get_height())
            for x in range(surface.get_width())
            if data[y * stride + x * 4 + 3] > 200
        ]
        return max(values)

    assert brightest_ink(dark_text) < 60
    assert brightest_ink(light_text) > 200


def test_cache_key_includes_the_colour() -> None:
    formula = mathimg.Formula("a", False)
    assert mathimg.cache_path(formula, fg="#000000") != mathimg.cache_path(formula, fg="#ffffff")
    assert mathimg.cache_path(formula) == mathimg.cache_path(formula, fg=mathimg.DEFAULT_FG)
