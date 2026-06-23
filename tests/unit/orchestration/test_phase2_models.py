from __future__ import annotations

import pytest

from ocop_pack.orchestration.budgets import BudgetPolicy, BudgetTracker
from ocop_pack.orchestration.errors import WorkflowException
from ocop_pack.orchestration.idempotency import completed, idempotency_key, mark_completed
from ocop_pack.orchestration.routing import route_after_approval
from ocop_pack.orchestration.state import ApprovalRecord, initial_state
from ocop_pack.orchestration.status import RunStatus, assert_transition


def test_state_defaults_are_serializable() -> None:
    state = initial_state("run1", "project.yaml")
    assert state["status"] == RunStatus.CREATED
    assert state["completed_nodes"] == []


def test_valid_and_invalid_status_transitions() -> None:
    assert_transition(RunStatus.CREATED, RunStatus.INPUT_VALIDATED)
    with pytest.raises(ValueError):
        assert_transition(RunStatus.EXPORTED, RunStatus.CREATED)


def test_routing_after_approval() -> None:
    state = initial_state("run1", "project.yaml")
    state["status"] = RunStatus.APPROVED
    assert route_after_approval(state) == "render_final_outputs"
    state["status"] = RunStatus.REJECTED
    assert route_after_approval(state) == "rejected"


def test_budget_boundaries() -> None:
    state = initial_state("run1", "project.yaml")
    tracker = BudgetTracker(BudgetPolicy(max_candidates=2))
    tracker.check(state, "node", candidate_count=2)
    with pytest.raises(WorkflowException):
        tracker.check(state, "node", candidate_count=3)


def test_idempotency_key_and_completed_nodes() -> None:
    assert idempotency_key("node", ["b", "a"]) == idempotency_key("node", ["a", "b"])
    nodes = mark_completed([], "node")
    assert completed(nodes, "node")
    assert mark_completed(nodes, "node") == nodes


def test_approval_hash_validation_shape() -> None:
    record = ApprovalRecord(
        run_id="run1",
        candidate_id="C001",
        candidate_hash="abc",
        project_hash="def",
        approved_by="tester",
        decision="approve",
    )
    assert record.model_dump()["candidate_hash"] == "abc"
