from __future__ import annotations

from hashlib import sha256

from pydantic import BaseModel

from ocop_pack.agents.design_planner.prompt_registry import PromptDescriptor, load_prompt
from ocop_pack.domain.project import ProjectSpec


class PlannerInput(BaseModel):
    project_id: str
    product_summary: dict[str, str]
    brand_summary: dict[str, object]
    size_profile: str
    panel_structure_summary: str
    content_density_summary: str
    allowed_enums: dict[str, list[str]]
    prohibited_content: list[str]


def build_planner_input(project: ProjectSpec) -> PlannerInput:
    return PlannerInput(
        project_id=project.project_id,
        product_summary={
            "category": project.product.category,
            "net_content": project.product.net_content,
        },
        brand_summary={
            "logo_count": len(project.branding.logos),
            "ocop_star_count": project.branding.ocop.star_count,
        },
        size_profile=project.packaging.size_id,
        panel_structure_summary="full spread with left/center/right panels and fold safety zones",
        content_density_summary="medium" if len(project.product.ingredients) < 180 else "high",
        allowed_enums={
            "artwork_strategy": [
                "full_bleed_continuous",
                "center_hero",
                "split_botanical",
            ],
            "panel_strategy": [
                "center_focus_vertical_sides",
                "center_lockup_balanced_sides",
                "asymmetric_center_with_qr_side",
            ],
            "logo_cluster": [
                "top_center",
                "top_split",
                "center_header",
            ],
            "side_text_mode": [
                "vertical",
                "horizontal_compact",
                "mixed",
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


def default_prompts() -> list[PromptDescriptor]:
    return [load_prompt("system"), load_prompt("planner")]
