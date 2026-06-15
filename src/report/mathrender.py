"""
mathrender.py - Render LaTeX math expressions to PNG using matplotlib mathtext,
and wrap them as ReportLab Image flowables for the PDF report.

The same LaTeX strings are rendered by KaTeX in the Streamlit UI (st.latex),
so the app and the report show identical worked formulas.
"""
from __future__ import annotations
import io
import functools

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.platypus import Image, Paragraph
from reportlab.lib.units import mm

_DPI = 200


@functools.lru_cache(maxsize=1024)
def latex_png(latex: str, fontsize: int = 11, color: str = "#1A2733") -> bytes | None:
    """Render a LaTeX expression to transparent PNG bytes. Returns None on failure."""
    fig = plt.figure(figsize=(0.01, 0.01))
    try:
        fig.text(0, 0, f"${latex}$", fontsize=fontsize, color=color)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_DPI, bbox_inches="tight",
                    pad_inches=0.04, transparent=True)
        plt.close(fig)
        return buf.getvalue()
    except Exception:
        plt.close(fig)
        return None


def latex_flowable(latex: str, max_w_mm: float = 155.0, fontsize: int = 10,
                   fallback_style=None):
    """
    Return a ReportLab flowable for a LaTeX expression: an Image if the math
    renders, otherwise a plain Paragraph fallback (so the report never breaks).
    """
    png = latex_png(latex, fontsize)
    if png is None:
        if fallback_style is not None:
            safe = latex.replace("\\", "").replace("{", "").replace("}", "")
            return Paragraph(safe, fallback_style)
        return None
    # px -> pt (matplotlib saved at _DPI; 1 pt = 1/72 in)
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(io.BytesIO(png)).getSize()
    scale = 72.0 / _DPI
    w, h = iw * scale, ih * scale
    max_w = max_w_mm * mm
    if w > max_w:
        r = max_w / w
        w, h = w * r, h * r
    return Image(io.BytesIO(png), width=w, height=h)
