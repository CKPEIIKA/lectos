"""Approximate LaTeX math with Unicode for terminals. Lossy by design; unknown macros stay as written."""

from __future__ import annotations

import re

SYMBOLS = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε", "zeta": "ζ",
    "eta": "η", "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν",
    "xi": "ξ", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "upsilon": "υ", "phi": "φ", "varphi": "φ",
    "chi": "χ", "psi": "ψ", "omega": "ω", "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ",
    "Pi": "Π", "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
    "partial": "∂", "nabla": "∇", "infty": "∞", "cdot": "·", "times": "×", "pm": "±", "mp": "∓",
    "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠", "approx": "≈", "sim": "∼", "equiv": "≡",
    "propto": "∝", "to": "→", "rightarrow": "→", "leftarrow": "←", "Rightarrow": "⇒", "Leftarrow": "⇐",
    "leftrightarrow": "↔", "mapsto": "↦", "in": "∈", "notin": "∉", "subset": "⊂", "subseteq": "⊆",
    "cup": "∪", "cap": "∩", "forall": "∀", "exists": "∃", "emptyset": "∅", "sum": "Σ", "prod": "Π",
    "int": "∫", "oint": "∮", "ldots": "…", "cdots": "⋯", "dots": "…", "otimes": "⊗", "oplus": "⊕",
    "langle": "⟨", "rangle": "⟩", "lvert": "|", "rvert": "|", "vert": "|", "Vert": "‖", "lVert": "‖",
    "rVert": "‖", "ell": "ℓ", "hbar": "ħ", "log": "log", "ln": "ln", "sin": "sin", "cos": "cos", "tan": "tan",
    "exp": "exp", "max": "max", "min": "min", "lim": "lim", "det": "det", "quad": "  ", "qquad": "    ",
}  # fmt: skip
ACCENTS = {"hat": "\u0302", "tilde": "\u0303", "bar": "\u0304", "vec": "\u20d7", "dot": "\u0307", "ddot": "\u0308"}
WRAPPERS = ("mathbf", "mathrm", "mathcal", "mathbb", "boldsymbol", "bm", "text", "mathit", "operatorname")
SUP = str.maketrans("0123456789+-=()ni", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ")
SUB = str.maketrans("0123456789+-=()aeoxhklmnpst", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₕₖₗₘₙₚₛₜ")
_NESTING_PASSES = 5
_FRAC_SHORT_RE = re.compile(r"\\[dt]?frac\s*(\d)\s*(\d)")
_FRAC_RE = re.compile(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_SQRT_RE = re.compile(r"\\sqrt\s*\{([^{}]*)\}")
_WRAP_RE = re.compile(r"\\(?:" + "|".join(WRAPPERS) + r")\s*(?:\{([^{}]*)\}|([A-Za-z]))")
_ACCENT_RE = re.compile(r"\\(" + "|".join(ACCENTS) + r")\s*(?:\{([^{}])\}|([A-Za-z]))")
_MACRO_RE = re.compile(r"\\([A-Za-z]+)")
_SCRIPT_RE = re.compile(r"([\^_])(?:\{([^{}]*)\}|(\\[A-Za-z]+|.))")
_SINGLE_RE = re.compile(r"[\w.]+|\([^()]*\)")


def _paren(text: str) -> str:
    return text if _SINGLE_RE.fullmatch(text.strip()) else f"({text.strip()})"


def _script(match: re.Match[str]) -> str:
    kind, body = match.group(1), match.group(2) if match.group(2) is not None else match.group(3)
    table = SUP if kind == "^" else SUB
    mapped = body.translate(table)
    if all(not ch.isascii() or not ch.isalnum() for ch in mapped) and not body.startswith("\\"):
        return mapped
    return f"{kind}{body}" if len(body) == 1 or body.startswith("\\") else f"{kind}({body})"


def to_unicode(tex: str) -> str:
    """Convert LaTeX math source to a one-line Unicode approximation."""
    text = re.sub(r"\\(?:left|right|big|Big|bigg|Bigg)\b", "", tex)
    text = re.sub(r"\\[,;:! ]", " ", text)
    text = _MACRO_RE.sub(lambda m: SYMBOLS.get(m.group(1), m.group(0)), text)  # before unwrapping, so tokens never glue
    for _ in range(_NESTING_PASSES):
        text = _WRAP_RE.sub(lambda m: m.group(1) or m.group(2), text)
        text = _FRAC_SHORT_RE.sub(lambda m: f"{m.group(1)}/{m.group(2)}", text)
        text = _FRAC_RE.sub(lambda m: f"{_paren(m.group(1))}/{_paren(m.group(2))}", text)
        text = _SQRT_RE.sub(lambda m: f"√{_paren(m.group(1))}", text)
    text = _ACCENT_RE.sub(lambda m: (m.group(2) or m.group(3) or "") + ACCENTS[m.group(1)], text)
    text = _SCRIPT_RE.sub(_script, text)
    return re.sub(r"\s+", " ", text.replace("{", "").replace("}", "")).strip()
