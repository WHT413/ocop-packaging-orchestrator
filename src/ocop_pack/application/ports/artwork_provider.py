from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from ocop_pack.provenance.models import ArtworkProvenance, ProviderContext


class ArtworkRequest(BaseModel):
    concept_id: str
    prompt: str
    negative_prompt: str
    target_width_px: int
    target_height_px: int
    output_format: str = "png"
    seed: int | None = None
    quality: str = "standard"
    background_mode: str = "opaque"
    request_hash: str


class ArtworkResult(BaseModel):
    artifact_ref: str
    provider: str
    model: str
    request_id: str
    prompt_hash: str
    revised_prompt: str | None = None
    width: int
    height: int
    format: str
    sha256: str
    latency_ms: int = 0
    cost_estimate: float = 0.0
    usage: dict[str, int] = Field(default_factory=dict)
    safety_metadata: dict[str, object] = Field(default_factory=dict)
    provenance: ArtworkProvenance | None = None


class ImageProvider(Protocol):
    def generate(
        self, request: ArtworkRequest, context: ProviderContext, output_dir: Path
    ) -> ArtworkResult: ...
