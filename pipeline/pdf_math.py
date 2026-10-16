"""Display formulas for the PDF renderer: LaTeX (`$$ … $$`) → PNG via matplotlib mathtext.

mathtext is a pure-Python subset of LaTeX, so no TeX installation is needed. It cannot
parse everything (environments such as `aligned`, `\\begin{cases}`, …): such formulas are
reported to the caller, which falls back to monospace LaTeX source – never silently dropped.
Output is deterministic (fixed font set, fixed dpi, no timestamps in the PNG).
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")                      # headless; must precede the pyplot import
from matplotlib import mathtext            # noqa: E402
from matplotlib.figure import Figure       # noqa: E402

DPI = 300
FONT_SIZE = 14                             # pt; matches the 10.5 pt body text visually
# mathtext spellings that LaTeX authors commonly use but mathtext lacks.
_ALIASES = (
    (r"\\dfrac|\\tfrac", r"\\frac"),
    (r"\\left\\\{", r"\\{"), (r"\\right\\\}", r"\\}"),
    (r"\\left\.|\\right\.", ""),
    (r"\\quad|\\qquad", r"\\ \\ "),
    (r"\\!", ""),
    (r"\\displaystyle\s*", ""),
)
_LINE_BREAK = re.compile(r"\\\\\s*")


@dataclass(frozen=True)
class FormulaImage:
    png: bytes
    width_pt: float                        # natural width in PDF points
    height_pt: float


def normalise(latex: str) -> str:
    out = latex.strip()
    for pattern, repl in _ALIASES:
        out = re.sub(pattern, repl, out)
    return re.sub(r"\s+", " ", out)


def split_lines(latex: str) -> list[str]:
    """`a \\\\ b` (LaTeX line break) → separate lines, each rendered on its own."""
    return [part for part in (normalise(p) for p in _LINE_BREAK.split(latex)) if part]


def render_line(latex: str) -> FormulaImage | None:
    """One mathtext line → PNG, or None when mathtext cannot parse it."""
    expr = f"${latex}$"
    try:
        mathtext.MathTextParser("path").parse(expr, dpi=DPI, prop=None)
        fig = Figure(figsize=(0.01, 0.01), dpi=DPI)
        fig.text(0, 0, expr, fontsize=FONT_SIZE)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=DPI, bbox_inches="tight", pad_inches=0.04,
                    transparent=True, metadata={"Software": None})
    except Exception:                      # mathtext raises ValueError/ParseFatalException
        return None
    return _measure(buf.getvalue())


def _measure(png: bytes) -> FormulaImage:
    from PIL import Image
    with Image.open(io.BytesIO(png)) as im:
        w, h = im.size
    return FormulaImage(png, w * 72 / DPI, h * 72 / DPI)


def render_formula(latex: str) -> list[FormulaImage] | None:
    """All lines of a display formula, or None if any line is unparseable (→ fallback)."""
    images = []
    for line in split_lines(latex):
        image = render_line(line)
        if image is None:
            return None
        images.append(image)
    return images or None
