from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ocop_pack.domain.geometry import BoundingBox
from ocop_pack.domain.layout import LayoutManifest


class SceneElement(BaseModel):
    element_id: str
    kind: Literal["text", "image", "qr", "shape", "vector", "group"]
    source_ref: str
    bbox_mm: BoundingBox
    rotation_deg: int = 0
    z_index: int = 0
    critical: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


ImageElement = SceneElement
TextElement = SceneElement
VectorElement = SceneElement
ShapeElement = SceneElement
QrElement = SceneElement


class SceneGroup(BaseModel):
    group_id: str
    elements: list[SceneElement]
    metadata: dict[str, Any] = Field(default_factory=dict)


class Scene(BaseModel):
    run_id: str
    project_id: str
    width_mm: float
    height_mm: float
    elements: list[SceneElement]
    metadata: dict[str, Any] = Field(default_factory=dict)


def scene_from_manifest(manifest: LayoutManifest, width_mm: float, height_mm: float) -> Scene:
    return Scene(
        run_id=manifest.run_id,
        project_id=manifest.project_id,
        width_mm=width_mm,
        height_mm=height_mm,
        elements=[SceneElement.model_validate(e.model_dump()) for e in manifest.candidate.elements],
        metadata={
            "candidate_id": manifest.candidate.candidate_id,
            "artwork_refs": manifest.artwork_refs,
            "artwork_hashes": manifest.artwork_hashes,
            "visual_theme": manifest.candidate.metadata.get("visual_theme", {}),
            **manifest.metadata,
        },
    )
