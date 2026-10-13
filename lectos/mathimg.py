"""LaTeX formulas to PNG images: one batched ``latex`` run plus ``dvipng``, cached on disk."""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

TOOL_TIMEOUT_S = 60.0
MATH_DPI = 110
MAX_FORMULAS = 400
MAX_FORMULA_CHARS = 2000
PREAMBLE = (
    "\\documentclass[12pt]{article}\n\\usepackage{amsmath,amssymb,amsfonts,bm}\n\\pagestyle{empty}\n\\begin{document}\n"
)


@dataclass(frozen=True)
class Formula:
    """A LaTeX math expression and whether it is set as a display equation."""

    tex: str
    display: bool

    @property
    def source(self) -> str:
        """The TeX source of one page."""
        return f"\\[{self.tex}\\]" if self.display else f"\\({self.tex}\\)"


def cache_dir() -> Path:
    """Directory holding compiled formula images."""
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "lectos" / "math"


def cache_path(formula: Formula, dpi: int = MATH_DPI) -> Path:
    """Cache file for the formula, keyed by source, preamble and resolution."""
    digest = hashlib.sha256(f"{PREAMBLE}|{formula.source}|{dpi}".encode()).hexdigest()[:24]
    return cache_dir() / f"{digest}.png"


def _compile(formulas: list[Formula], dpi: int) -> list[bytes] | None:
    """Compile formulas into one document; return one PNG per formula, or None on any failure."""
    body = "\\newpage\n".join(f"{f.source}\n" for f in formulas)
    env = {**os.environ, "openin_any": "p", "openout_any": "p"}  # TeX paranoid file access
    with tempfile.TemporaryDirectory(prefix="lectos-tex-") as tmp:
        work = Path(tmp)
        (work / "m.tex").write_text(f"{PREAMBLE}{body}\\end{{document}}\n", encoding="utf-8")
        steps = [
            ["latex", "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape", "m.tex"],
            ["dvipng", "-D", str(dpi), "-T", "tight", "-bg", "Transparent", "-o", "p%d.png", "m.dvi"],
        ]
        for step in steps:
            try:
                done = subprocess.run(step, cwd=work, env=env, capture_output=True, timeout=TOOL_TIMEOUT_S, check=False)
            except (OSError, subprocess.TimeoutExpired):
                return None
            if done.returncode != 0:
                return None
        pages = [work / f"p{i}.png" for i in range(1, len(formulas) + 1)]
        return [p.read_bytes() for p in pages] if all(p.exists() for p in pages) else None


def render(formulas: list[Formula], dpi: int = MATH_DPI) -> dict[Formula, Path]:
    """Return image files for the formulas that compile. Failures are omitted, never fatal."""
    unique = [f for f in dict.fromkeys(formulas) if len(f.tex) <= MAX_FORMULA_CHARS][:MAX_FORMULAS]
    missing = [f for f in unique if not cache_path(f, dpi).exists()]
    if missing:
        cache_dir().mkdir(parents=True, exist_ok=True)
        batch = _compile(missing, dpi)
        groups = [([f], [png]) for f, png in zip(missing, batch, strict=True)] if batch else []
        if not batch:  # one bad formula must not hide the rest: retry individually
            for f in missing:
                one = _compile([f], dpi)
                if one:
                    groups.append(([f], one))
        for fs, pngs in groups:
            cache_path(fs[0], dpi).write_bytes(pngs[0])
    return {f: cache_path(f, dpi) for f in unique if cache_path(f, dpi).exists()}
