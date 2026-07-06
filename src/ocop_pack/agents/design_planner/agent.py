from __future__ import annotations

from hashlib import sha256

from pydantic import BaseModel, Field

from ocop_pack.agents.design_planner.prompt_registry import PromptDescriptor, load_prompt
from ocop_pack.domain.project import ProjectSpec


class PlannerInput(BaseModel):
    project_id: str
    product_summary: dict[str, str]
    creative_brief_raw: str = Field(default="", max_length=4000)
    creative_brief_hash: str
    brand_summary: dict[str, object]
    size_profile: str
    panel_structure_summary: str
    content_density_summary: str
    allowed_enums: dict[str, list[str]]
    prohibited_content: list[str]


def build_planner_input(project: ProjectSpec) -> PlannerInput:
    creative_brief = project.creative_brief_raw.strip()
    return PlannerInput(
        project_id=project.project_id,
        product_summary={
            "category": project.product.category,
            "net_content": project.product.net_content,
        },
        creative_brief_raw=creative_brief,
        creative_brief_hash=sha256(creative_brief.encode("utf-8")).hexdigest(),
        brand_summary={
            "logo_count": len(project.branding.logos),
            "ocop_star_count": project.branding.ocop.star_count,
        },
        size_profile=project.packaging.size_id,
        panel_structure_summary="full spread with left/center/right panels and fold safety zones",
        content_density_summary="medium" if len(project.product.ingredients) < 180 else "high",
        allowed_enums={
            "artwork_strategy": [
                "softened_full_background",
                "framed_hero_region",
                "panel_local_decorative_strip",
            ],
            "panel_strategy": [
                "center_focus_vertical_sides",
                "center_lockup_balanced_sides",
                "asymmetric_center_with_qr_side",
            ],
            "side_text_mode": [
                "vertical",
                "horizontal_compact",
                "mixed",
            ],
            "panel_roles": [
                "center_primary_sides_secondary",
                "center_primary_left_info_right_traceability",
            ],
            "content_hierarchy": ["title_first", "logo_title_info"],
            "title_block_intent": ["hero_label_card", "stacked_brand_title_card"],
            "info_block_intent": ["side_label_cards", "compact_traceability_card"],
            "protected_zone_strategy": ["guard_all_critical_text", "center_safe_title_zone"],
            "contrast_strategy": ["opaque_light_cards", "semi_opaque_warm_scrims"],
            "frame_style": [
                "theme_default",
                "paper_label",
                "soft_scrim",
                "kraft_card",
                "premium_badge",
                "torn_paper",
                "leaf_badge",
                "woven_label",
                "vellum_overlay",
                "brush_stroke",
                "natural_reference_mix",
            ],
            "font_mood": [
                "theme_default",
                "functional_safe",
                "refined_natural",
                "artisanal_bold",
            ],
            "contrast_style": [
                "theme_default",
                "light_scrim",
                "balanced_scrim",
                "opaque_card",
            ],
        },
        prohibited_content=[
            "text",
            "logo",
            "OCOP logo",
            "star icons",
            "QR",
            "barcode",
            "phone",
            "legal claim",
        ],
    )


def planner_input_hash(planner_input: PlannerInput, prompts: list[PromptDescriptor]) -> str:
    payload = planner_input.model_dump_json() + "".join(p.sha256 for p in prompts)
    return sha256(payload.encode("utf-8")).hexdigest()


def planner_prompt_hash(prompts: list[PromptDescriptor]) -> str:
    return sha256("".join(p.sha256 for p in prompts).encode("utf-8")).hexdigest()


def default_prompts() -> list[PromptDescriptor]:
    return [load_prompt("system"), load_prompt("planner")]
