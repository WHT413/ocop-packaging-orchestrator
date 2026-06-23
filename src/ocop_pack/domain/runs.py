from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
    CREATED = "created"
    CANDIDATES_GENERATED = "candidates_generated"
    RENDERED = "rendered"
    QA_PASSED = "qa_passed"
    QA_FAILED = "qa_failed"
    FAILED = "failed"


class RunRecord(BaseModel):
    run_id: str
    project_id: str
    input_hash: str
    dieline_version: str
    status: RunStatus = RunStatus.CREATED
    metadata: dict[str, Any] = Field(default_factory=dict)
