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
    creative_brief_hash: str = ""
    system_prompt_hash: str = ""
    task_prompt_hash: str = ""
    planner_policy_version: str = ""
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
    original_width: int | None = None
    original_height: int | None = None
    normalization_policy: str | None = None
    latency_ms: int = 0
    cost_estimate: float = 0.0
    cache_hit: bool = False
    warning_codes: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class CriticProvenance(BaseModel):
    contact_sheet_hash: str
    candidate_hashes: dict[str, str]
    prompt_id: str
    prompt_version: str
    prompt_hash: str
    rubric_version: str
    schema_version: str
    provider: str
    model: str
    provider_request_id: str
    usage: UsageRecord = Field(default_factory=UsageRecord)
    latency_ms: int = 0
    cost_estimate: float = 0.0
    cache_hit: bool = False
    decision_hash: str
    raw_response_hash: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class RevisionProvenance(BaseModel):
    parent_artwork_id: str
    parent_artwork_hash: str
    issue_code: str
    instruction_hash: str
    prohibited_content_hash: str
    provider: str
    model: str
    provider_request_id: str
    result_hash: str
    width: int
    height: int
    cost_estimate: float = 0.0
    latency_ms: int = 0
    cache_hit: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
