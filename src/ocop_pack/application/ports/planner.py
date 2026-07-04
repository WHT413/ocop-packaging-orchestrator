from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from ocop_pack.agents.design_planner.agent import PlannerInput
from ocop_pack.provenance.models import PlannerProvenance, ProviderContext
from ocop_pack.schemas.design_planner import DesignPlan


class PlannerRequest(BaseModel):
    planner_input: PlannerInput
    prompt_id: str
    prompt_version: str
    prompt_hash: str
    system_prompt_hash: str = ""
    task_prompt_hash: str = ""
    creative_brief_hash: str = ""
    planner_policy_version: str = "design-planner-policy.v2"
    input_hash: str
    model_config_payload: dict[str, object] = Field(default_factory=dict)


class PlannerResult(BaseModel):
    design_plan: DesignPlan
    provenance: PlannerProvenance


class PlannerProvider(Protocol):
    def create_design_plan(
        self, request: PlannerRequest, context: ProviderContext
    ) -> PlannerResult: ...
