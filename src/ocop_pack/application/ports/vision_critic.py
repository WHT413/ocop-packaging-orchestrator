from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from ocop_pack.agents.visual_critic.schemas import CriticDecision
from ocop_pack.provenance.models import CriticProvenance, ProviderContext, UsageRecord


class CriticRequest(BaseModel):
    contact_sheet_path: Path
    contact_sheet_hash: str
    candidate_ids: list[str]
    candidate_hashes: dict[str, str]
    artwork_ids: list[str]
    brand_summary: str
    visual_direction: str
    product_category: str
    layout_intent_summary: str
    hard_constraint_summary: str
    prompt_id: str
    prompt_version: str
    prompt_hash: str
    schema_version: str
    rubric_version: str
    request_hash: str


class CriticResult(BaseModel):
    decision: CriticDecision
    provider: str
    model_id: str
    provider_request_id: str
    contact_sheet_hash: str
    prompt_id: str
    prompt_version: str
    prompt_hash: str
    schema_version: str
    usage: UsageRecord = Field(default_factory=UsageRecord)
    latency_ms: int = 0
    cost_estimate: float = 0.0
    raw_response_hash: str = ""
    provenance: CriticProvenance | None = None


class VisionCriticProvider(Protocol):
    def evaluate(self, request: CriticRequest, context: ProviderContext) -> CriticResult: ...
