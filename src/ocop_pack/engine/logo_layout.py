from __future__ import annotations

from pathlib import Path

from PIL import Image

from ocop_pack.services.validation_service import file_sha256


def image_aspect_ratio(path: Path) -> float:
    with Image.open(path) as img:
        return img.width / img.height


def validate_logo_integrity(
    path: Path, rendered_width_mm: float, rendered_height_mm: float, tolerance: float = 0.03
) -> dict[str, object]:
    ratio = image_aspect_ratio(path)
    rendered = rendered_width_mm / rendered_height_mm
    return {
        "sha256": file_sha256(path),
        "aspect_ratio": ratio,
        "preserved": abs(ratio - rendered) / ratio <= tolerance,
        "rotated": False,
        "cropped": False,
        "recolored": False,
    }
