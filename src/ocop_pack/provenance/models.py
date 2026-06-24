from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class UsageRecord(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ProviderContext(BaseModel):
    run_id: str
    thread_id: str
    node: str


class PlannerProvenance(BaseModel):
    provider: str
    model: str
    provider_request_id: str
    prompt_id: str
    prompt_version: str
    prompt_hash: str
    schema_version: str
    input_hash: str
    raw_response_hash: str
    usage: UsageRecord = Field(default_factory=UsageRecord)
    latency_ms: int = 0
    cost_estimate: float = 0.0
    cache_hit: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class ArtworkProvenance(BaseModel):
    artifact_id: str
    artifact_sha256: str
    provider: str
    model: str
    provider_request_id: str
    prompt_id: str
    prompt_version: str
    prompt_hash: str
    negative_prompt_hash: str
    input_hash: str
    width: int
    height: int
    format: str
    latency_ms: int = 0
    cost_estimate: float = 0.0
    cache_hit: bool = False
    warning_codes: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
