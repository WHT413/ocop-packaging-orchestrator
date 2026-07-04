from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from ocop_pack.agents.visual_critic.schemas import TargetedRevision
from ocop_pack.provenance.models import ProviderContext, RevisionProvenance


class ArtworkRevisionRequest(BaseModel):
    source_artwork_path: Path
    source_artwork_id: str
    source_artwork_hash: str
    targeted_revision: TargetedRevision
    visual_direction: str
    target_width_px: int
    target_height_px: int
    request_hash: str


class RevisedArtworkArtifact(BaseModel):
    artifact_ref: str
    artifact_id: str
    sha256: str
    width: int
    height: int
    format: str = "png"
    provider: str
    model: str
    request_id: str
    latency_ms: int = 0
    cost_estimate: float = 0.0
    provenance: RevisionProvenance | None = None


class ArtworkRevisionProvider(Protocol):
    def revise(
        self,
        request: ArtworkRevisionRequest,
        context: ProviderContext,
        output_dir: Path,
    ) -> RevisedArtworkArtifact: ...
