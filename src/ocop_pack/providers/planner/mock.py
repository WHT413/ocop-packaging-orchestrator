from __future__ import annotations

from hashlib import sha256

from ocop_pack.application.ports.planner import PlannerRequest, PlannerResult
from ocop_pack.provenance.models import PlannerProvenance, ProviderContext
from ocop_pack.schemas.design_planner import ArtworkConcept, DesignPlan, LayoutIntent


class MockPlannerProvider:
    provider = "mock"
    model = "mock-planner-v2"

    def create_design_plan(
        self, request: PlannerRequest, context: ProviderContext
    ) -> PlannerResult:
        brief = request.planner_input.creative_brief_raw.lower()
        is_honey = (
            "honey" in request.planner_input.product_summary.get("category", "").lower()
            or "mật ong" in brief
            or "honey" in brief
        )
        palette = ["tea green", "warm ivory", "deep leaf"]
        visual_direction = "clean botanical premium OCOP packaging"
        motifs = ["regional botanical texture", "craft material grain"]
        conflicts: list[str] = []
        if "vàng nâu" in brief or "brown" in brief:
            palette = ["warm amber", "golden brown", "soft ivory"]
        if "sang" in brief or "premium" in brief or "tự nhiên" in brief or "natural" in brief:
            visual_direction = "premium natural packaging with warm craft cues"
        if is_honey:
            motifs = ["amber honey glow", "honeycomb geometry", "wildflowers"]
        if "change star" in brief or "qr" in brief or "claim" in brief:
            conflicts.append(
                "Unsupported request attempted to alter protected factual, traceability, "
                "claim, or certification content."
            )
        concept_prompt = ", ".join([*motifs, "decorative artwork layer"])
        plan = DesignPlan(
            visual_direction=visual_direction,
            palette=palette,
            decorative_motifs=motifs,
            artwork_density="balanced",
            negative_space_intent="balanced",
            creative_assumptions=[]
            if request.planner_input.creative_brief_raw
            else ["No creative brief supplied; using deterministic defaults."],
            conflicts_or_unsupported_preferences=conflicts,
            artwork_concepts=[
                ArtworkConcept(
                    concept_id="A01",
                    description="Safe product-inspired decorative background.",
                    prompt=concept_prompt,
                    negative_prompt="no text, no letters, no logos, no QR codes, no barcodes",
                    artwork_strategy="softened_full_background",
                ),
                ArtworkConcept(
                    concept_id="A02",
                    description="Alternate safe decorative motif crop.",
                    prompt=concept_prompt,
                    negative_prompt="no text, no letters, no logos, no QR codes, no barcodes",
                    artwork_strategy="panel_local_decorative_strip",
                ),
            ],
            layout_intents=[
                LayoutIntent(
                    panel_strategy="center_lockup_balanced_sides",
                    side_text_mode="mixed",
                    artwork_strategy="softened_full_background",
                    panel_roles="center_primary_left_info_right_traceability",
                    content_hierarchy="title_first",
                    title_block_intent="hero_label_card",
                    info_block_intent="side_label_cards",
                    protected_zone_strategy="guard_all_critical_text",
                    contrast_strategy="semi_opaque_warm_scrims",
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
            creative_brief_hash=request.creative_brief_hash,
            system_prompt_hash=request.system_prompt_hash,
            task_prompt_hash=request.task_prompt_hash,
            planner_policy_version=request.planner_policy_version,
            raw_response_hash=raw_hash,
        )
        return PlannerResult(design_plan=plan, provenance=prov)
