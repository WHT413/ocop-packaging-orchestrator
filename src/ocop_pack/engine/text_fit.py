from __future__ import annotations

from PIL import ImageFont
from pydantic import BaseModel

from ocop_pack.domain.geometry import BoundingBox


class FontSpec(BaseModel):
    name: str = "DejaVuSans"
    path: str | None = None


class TextFitResult(BaseModel):
    fits: bool
    font_size_pt: float
    lines: list[str]
    rendered_bbox: BoundingBox
    overflow_reason: str | None = None


def _font(size: int, spec: FontSpec) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(spec.path or "DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def fit_text(
    text: str,
    bbox: BoundingBox,
    font: FontSpec,
    min_font_size_pt: float,
    max_font_size_pt: float,
    rotation_deg: int = 0,
) -> TextFitResult:
    max_w, max_h = (
        (bbox.height_mm, bbox.width_mm)
        if rotation_deg in {90, 270}
        else (bbox.width_mm, bbox.height_mm)
    )
    for size in range(int(max_font_size_pt), int(min_font_size_pt) - 1, -1):
        _font(size, font)
        words = text.split()
        lines: list[str] = []
        line = ""
        # 1 pt is approximated as 0.3528 mm for deterministic layout checks.
        char_mm = size * 0.3528 * 0.52
        line_h = size * 0.3528 * 1.2
        for word in words:
            candidate = f"{line} {word}".strip()
            if len(candidate) * char_mm <= max_w:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        rendered = BoundingBox(
            x_mm=bbox.x_mm,
            y_mm=bbox.y_mm,
            width_mm=min(max_w, max((len(line_text) for line_text in lines), default=0) * char_mm),
            height_mm=len(lines) * line_h,
        )
        if rendered.width_mm <= max_w and rendered.height_mm <= max_h:
            return TextFitResult(
                fits=True, font_size_pt=float(size), lines=lines, rendered_bbox=rendered
            )
    return TextFitResult(
        fits=False,
        font_size_pt=min_font_size_pt,
        lines=[text],
        rendered_bbox=bbox,
        overflow_reason="TEXT_OVERFLOW",
    )
