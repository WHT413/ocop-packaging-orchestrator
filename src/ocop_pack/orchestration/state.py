from __future__ import annotations

from datetime import UTC, datetime
from typing import TypedDict

from pydantic import BaseModel, Field

from ocop_pack.domain.project import ProjectSpec
from ocop_pack.orchestration.errors import WorkflowError
from ocop_pack.orchestration.status import RunStatus


class ApprovalRecord(BaseModel):
    run_id: str
    candidate_id: str
    candidate_hash: str
    project_hash: str
    approved_by: str
    approved_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    decision: str
    reason: str | None = None


class PackagingState(TypedDict):
    run_id: str
    thread_id: str
    project_path: str
    project_hash: str
    project: ProjectSpec | None
    planner_request_ref: str | None
    design_plan_ref: str | None
    design_plan_hash: str | None
    artwork_refs: list[str]
    artwork_hashes: dict[str, str]
    candidate_refs: list[str]
    selected_candidate_id: str | None
    selected_candidate_hash: str | None
    preview_refs: list[str]
    final_png_ref: str | None
    final_pdf_ref: str | None
    qa_report_ref: str | None
    approval: ApprovalRecord | None
    llm_calls: int
    image_calls: int
    vision_calls: int
    revision_count: int
    spent_estimate: float
    planner_provider: str | None
    planner_model: str | None
    image_provider: str | None
    image_model: str | None
    provider_attempts: int
    cache_hits: int
    token_usage: dict[str, int]
    completed_nodes: list[str]
    artifact_refs: dict[str, str]
    errors: list[WorkflowError]
    status: RunStatus


def initial_state(run_id: str, project_path: str, thread_id: str | None = None) -> PackagingState:
    return {
        "run_id": run_id,
        "thread_id": thread_id or run_id,
        "project_path": project_path,
        "project_hash": "",
        "project": None,
        "planner_request_ref": None,
        "design_plan_ref": None,
        "design_plan_hash": None,
        "artwork_refs": [],
        "artwork_hashes": {},
        "candidate_refs": [],
        "selected_candidate_id": None,
        "selected_candidate_hash": None,
        "preview_refs": [],
        "final_png_ref": None,
        "final_pdf_ref": None,
        "qa_report_ref": None,
        "approval": None,
        "llm_calls": 0,
        "image_calls": 0,
        "vision_calls": 0,
        "revision_count": 0,
        "spent_estimate": 0.0,
        "planner_provider": None,
        "planner_model": None,
        "image_provider": None,
        "image_model": None,
        "provider_attempts": 0,
        "cache_hits": 0,
        "token_usage": {},
        "completed_nodes": [],
        "artifact_refs": {},
        "errors": [],
        "status": RunStatus.CREATED,
    }
