from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from ocop_pack.orchestration.errors import WorkflowError, WorkflowException
from ocop_pack.orchestration.state import PackagingState


@dataclass(frozen=True)
class BudgetPolicy:
    max_llm_calls: int = 0
    max_image_calls: int = 0
    max_vision_calls: int = 0
    max_revisions: int = 3
    max_candidates: int = 50
    max_spent_estimate: float = 0.0
    max_elapsed_seconds: float = 300.0


class BudgetTracker:
    def __init__(self, policy: BudgetPolicy, started_at: float | None = None) -> None:
        self.policy = policy
        self.started_at = monotonic() if started_at is None else started_at

    def check(self, state: PackagingState, node: str, candidate_count: int = 0) -> None:
        failures: list[str] = []
        if state["llm_calls"] > self.policy.max_llm_calls:
            failures.append("llm_calls")
        if state["image_calls"] > self.policy.max_image_calls:
            failures.append("image_calls")
        if state["vision_calls"] > self.policy.max_vision_calls:
            failures.append("vision_calls")
        if state["revision_count"] > self.policy.max_revisions:
            failures.append("revision_count")
        if candidate_count > self.policy.max_candidates:
            failures.append("candidate_count")
        if state["spent_estimate"] > self.policy.max_spent_estimate:
            failures.append("spent_estimate")
        if monotonic() - self.started_at > self.policy.max_elapsed_seconds:
            failures.append("elapsed_time")
        if failures:
            raise WorkflowException(
                WorkflowError(
                    code="BUDGET_EXCEEDED",
                    message="budget exceeded: " + ", ".join(failures),
                    node=node,
                    details={"failures": failures},
                )
            )
