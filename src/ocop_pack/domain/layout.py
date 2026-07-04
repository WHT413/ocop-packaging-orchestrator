from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ocop_pack.domain.geometry import BoundingBox


class LayoutElement(BaseModel):
    element_id: str
    kind: Literal["text", "image", "qr", "shape", "vector", "group"]
    source_ref: str
    bbox_mm: BoundingBox
    rotation_deg: int = 0
    z_index: int = 0
    critical: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class LayoutCandidate(BaseModel):
    candidate_id: str
    template_id: str
    seed: int
    elements: list[LayoutElement]
    metadata: dict[str, Any] = Field(default_factory=dict)


class LayoutManifest(BaseModel):
    run_id: str
    project_id: str
    dieline_version: str
    candidate: LayoutCandidate
    artwork_refs: dict[str, str] = Field(default_factory=dict)
    artwork_hashes: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
