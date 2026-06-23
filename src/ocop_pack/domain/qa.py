from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ConstraintResult(BaseModel):
    rule_id: str
    passed: bool
    severity: Literal["critical", "warning"]
    element_ids: list[str]
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class QAReport(BaseModel):
    run_id: str
    candidate_id: str
    passed: bool
    results: list[ConstraintResult]
