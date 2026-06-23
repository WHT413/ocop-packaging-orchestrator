from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ArtifactMetadata(BaseModel):
    artifact_id: str
    run_id: str
    candidate_id: str | None = None
    kind: Literal["png", "pdf", "overlay", "qa", "manifest"]
    relative_path: str
    sha256: str
    metadata: dict[str, Any] = Field(default_factory=dict)
