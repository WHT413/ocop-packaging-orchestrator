from __future__ import annotations

from typing import Literal

from ocop_pack.domain.geometry import BoundingBox
from ocop_pack.domain.layout import LayoutElement


def compose_ocop_lockup(
    logo_source_ref: str,
    star_count: int,
    bbox: BoundingBox,
    alignment: Literal["horizontal", "vertical", "centered"] = "horizontal",
) -> LayoutElement:
    if not 1 <= star_count <= 5:
        raise ValueError("star_count must be 1..5")
    return LayoutElement(
        element_id="ocop_lockup",
        kind="group",
        source_ref=logo_source_ref,
        bbox_mm=bbox,
        critical=True,
        metadata={
            "star_count": star_count,
            "source": "user_provided",
            "verified_by_system": False,
            "alignment": alignment,
        },
    )
