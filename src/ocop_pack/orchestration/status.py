from __future__ import annotations

from enum import StrEnum


class RunStatus(StrEnum):
    CREATED = "CREATED"
    INPUT_VALIDATED = "INPUT_VALIDATED"
    DESIGN_INPUTS_READY = "DESIGN_INPUTS_READY"
    ARTWORK_READY = "ARTWORK_READY"
    CANDIDATES_READY = "CANDIDATES_READY"
    PREVIEWS_READY = "PREVIEWS_READY"
    DRAFT_QA_PASSED = "DRAFT_QA_PASSED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    FINAL_RENDERED = "FINAL_RENDERED"
    FINAL_QA_PASSED = "FINAL_QA_PASSED"
    EXPORTED = "EXPORTED"
    NEEDS_INPUT = "NEEDS_INPUT"
    FAILED_VALIDATION = "FAILED_VALIDATION"
    FAILED_LAYOUT = "FAILED_LAYOUT"
    FAILED_RENDER = "FAILED_RENDER"
    FAILED_QA = "FAILED_QA"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


TERMINAL_STATUSES = {
    RunStatus.EXPORTED,
    RunStatus.NEEDS_INPUT,
    RunStatus.FAILED_VALIDATION,
    RunStatus.FAILED_LAYOUT,
    RunStatus.FAILED_RENDER,
    RunStatus.FAILED_QA,
    RunStatus.BUDGET_EXCEEDED,
    RunStatus.REJECTED,
    RunStatus.CANCELLED,
}

_ALLOWED: dict[RunStatus, set[RunStatus]] = {
    RunStatus.CREATED: {
        RunStatus.INPUT_VALIDATED,
        RunStatus.FAILED_VALIDATION,
        RunStatus.NEEDS_INPUT,
    },
    RunStatus.INPUT_VALIDATED: {RunStatus.DESIGN_INPUTS_READY, RunStatus.BUDGET_EXCEEDED},
    RunStatus.DESIGN_INPUTS_READY: {RunStatus.ARTWORK_READY, RunStatus.BUDGET_EXCEEDED},
    RunStatus.ARTWORK_READY: {RunStatus.CANDIDATES_READY, RunStatus.FAILED_LAYOUT},
    RunStatus.CANDIDATES_READY: {RunStatus.PREVIEWS_READY, RunStatus.FAILED_LAYOUT},
    RunStatus.PREVIEWS_READY: {RunStatus.DRAFT_QA_PASSED, RunStatus.FAILED_QA},
    RunStatus.DRAFT_QA_PASSED: {RunStatus.WAITING_APPROVAL},
    RunStatus.WAITING_APPROVAL: {RunStatus.APPROVED, RunStatus.REJECTED, RunStatus.NEEDS_INPUT},
    RunStatus.APPROVED: {
        RunStatus.FINAL_RENDERED,
        RunStatus.FAILED_RENDER,
        RunStatus.BUDGET_EXCEEDED,
    },
    RunStatus.FINAL_RENDERED: {RunStatus.FINAL_QA_PASSED, RunStatus.FAILED_QA},
    RunStatus.FINAL_QA_PASSED: {RunStatus.EXPORTED, RunStatus.BUDGET_EXCEEDED},
}


def assert_transition(current: RunStatus, next_status: RunStatus) -> None:
    if current == next_status:
        return
    if current in TERMINAL_STATUSES or next_status not in _ALLOWED.get(current, set()):
        raise ValueError(f"invalid status transition: {current} -> {next_status}")
