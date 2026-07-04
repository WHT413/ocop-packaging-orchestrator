from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from ocop_pack.orchestration.errors import WorkflowError, WorkflowException
from ocop_pack.orchestration.state import PackagingState


@dataclass(frozen=True)
class BudgetPolicy:
    """
    Defines hard limits for workflow resource usage.

    The policy is consumed by ``BudgetTracker`` to stop a run when model calls,
    revision attempts, generated candidates, estimated spend, or elapsed time
    exceed the configured thresholds.

    Attributes:
        max_llm_calls: Maximum number of planner or text model calls allowed.
        max_image_calls: Maximum number of image generation calls allowed.
        max_vision_calls: Maximum number of visual critic calls allowed.
        max_revisions: Maximum number of revision cycles allowed.
        max_image_edit_calls: Maximum number of image edit calls allowed.
        max_candidates: Maximum number of layout candidates allowed.
        max_spent_estimate: Maximum estimated provider spend allowed.
        max_elapsed_seconds: Maximum elapsed runtime allowed in seconds.

    """

    max_llm_calls: int = 2
    max_image_calls: int = 3
    max_vision_calls: int = 0
    max_revisions: int = 0
    max_image_edit_calls: int = 0
    max_candidates: int = 50
    max_spent_estimate: float = 0.0
    max_elapsed_seconds: float = 300.0


class BudgetTracker:
    """
    Checks workflow state against a ``BudgetPolicy``.

    The tracker compares counters stored in ``PackagingState`` with the policy
    limits and raises ``WorkflowException`` when any budget is exceeded.

    Args:
        policy: Budget policy containing the limits to enforce.
        started_at: Optional monotonic timestamp used as the elapsed-time origin.
            When omitted, the tracker starts timing at construction time.

    Attributes:
        policy: Budget policy currently enforced by the tracker.
        started_at: Monotonic timestamp used to calculate elapsed runtime.

    """

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
        if state["image_edit_calls"] > self.policy.max_image_edit_calls:
            failures.append("image_edit_calls")
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
