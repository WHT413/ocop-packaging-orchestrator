from __future__ import annotations

from ocop_pack.orchestration.state import PackagingState
from ocop_pack.orchestration.status import RunStatus


def route_after_approval(state: PackagingState) -> str:
    if state["status"] == RunStatus.REJECTED:
        return "rejected"
    if state["status"] == RunStatus.NEEDS_INPUT:
        return "needs_input"
    if state["status"] == RunStatus.APPROVED:
        return "render_final_outputs"
    return "await_human_approval"
