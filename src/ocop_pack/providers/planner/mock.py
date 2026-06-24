from __future__ import annotations

from hashlib import sha256

from ocop_pack.application.ports.planner import PlannerRequest, PlannerResult
from ocop_pack.provenance.models import PlannerProvenance, ProviderContext
from ocop_pack.schemas.design_planner import ArtworkConcept, DesignPlan, LayoutIntent


class MockPlannerProvider:
    provider = "mock"
    model = "mock-planner-v1"

    def create_design_plan(
        self, request: PlannerRequest, context: ProviderContext
    ) -> PlannerResult:
        plan = DesignPlan(
            visual_direction="clean botanical premium OCOP packaging",
            palette=["tea green", "warm ivory", "deep leaf"],
            artwork_concepts=[
                ArtworkConcept(
                    concept_id="A01",
                    description="Soft tea leaves and regional texture as decorative background.",
                    prompt="decorative botanical tea leaves, watercolor texture, artwork layer",
                    negative_prompt="no text, no letters, no logos, no QR codes, no barcodes",
                    artwork_strategy="full_bleed_continuous",
                )
            ],
            layout_intents=[
                LayoutIntent(
                    panel_strategy="center_lockup_balanced_sides",
                    logo_cluster="top_center",
                    side_text_mode="mixed",
                    artwork_strategy="full_bleed_continuous",
                )
            ],
            prohibited_content=request.planner_input.prohibited_content,
            rationale="Deterministic offline plan for Phase 3 tests.",
        )
        raw_hash = sha256(plan.model_dump_json().encode("utf-8")).hexdigest()
        prov = PlannerProvenance(
            provider=self.provider,
            model=self.model,
            provider_request_id=f"mock-{context.run_id}",
            prompt_id=request.prompt_id,
            prompt_version=request.prompt_version,
            prompt_hash=request.prompt_hash,
            schema_version=plan.schema_version,
            input_hash=request.input_hash,
            raw_response_hash=raw_hash,
        )
        return PlannerResult(design_plan=plan, provenance=prov)
