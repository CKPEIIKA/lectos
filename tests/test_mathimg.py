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
