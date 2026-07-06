from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ArtworkStrategy = Literal[
    "softened_full_background",
    "framed_hero_region",
    "panel_local_decorative_strip",
]
FrameStyle = Literal[
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
]
FontMood = Literal[
    "theme_default",
    "functional_safe",
    "refined_natural",
    "artisanal_bold",
]
ContrastStyle = Literal[
    "theme_default",
    "light_scrim",
    "balanced_scrim",
    "opaque_card",
]


class ArtworkConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_id: str
    description: str
    prompt: str
    negative_prompt: str
    artwork_strategy: ArtworkStrategy = "softened_full_background"

    @field_validator("prompt", "negative_prompt", "description")
    @classmethod
    def no_geometry_or_controlled_content(cls, value: str) -> str:
        lowered = value.lower()
        forbidden = [
            " x=",
            " y=",
            "bbox",
            "bounding box",
            "coordinate",
            "font size",
            "qr position",
            "logo scale",
        ]
        if any(term in lowered for term in forbidden):
            raise ValueError("planner output must not contain final geometry")
        return value


class LayoutIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    panel_strategy: Literal[
        "center_focus_vertical_sides",
        "center_lockup_balanced_sides",
        "asymmetric_center_with_qr_side",
    ]
    side_text_mode: Literal[
        "vertical",
        "horizontal_compact",
        "mixed",
    ]
    artwork_strategy: ArtworkStrategy
    panel_roles: Literal[
        "center_primary_sides_secondary",
        "center_primary_left_info_right_traceability",
    ]
    content_hierarchy: Literal[
        "title_first",
        "logo_title_info",
    ]
    title_block_intent: Literal[
        "hero_label_card",
        "stacked_brand_title_card",
    ]
    info_block_intent: Literal[
        "side_label_cards",
        "compact_traceability_card",
    ]
    protected_zone_strategy: Literal[
        "guard_all_critical_text",
        "center_safe_title_zone",
    ]
    contrast_strategy: Literal[
        "opaque_light_cards",
        "semi_opaque_warm_scrims",
    ]
    frame_style: FrameStyle = "theme_default"
    font_mood: FontMood = "theme_default"
    contrast_style: ContrastStyle = "theme_default"


class DesignPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["design-plan.v2"] = "design-plan.v2"
    visual_direction: str
    palette: list[str] = Field(min_length=1, max_length=6)
    decorative_motifs: list[str] = Field(default_factory=list, max_length=8)
    artwork_density: Literal["minimal", "balanced", "rich"] = "balanced"
    negative_space_intent: Literal["open", "balanced", "dense"] = "balanced"
    creative_assumptions: list[str] = Field(default_factory=list, max_length=8)
    conflicts_or_unsupported_preferences: list[str] = Field(default_factory=list, max_length=8)
    artwork_concepts: list[ArtworkConcept] = Field(min_length=1, max_length=2)
    layout_intents: list[LayoutIntent] = Field(min_length=1, max_length=2)
    prohibited_content: list[str] = Field(default_factory=list)
    rationale: str

    @model_validator(mode="after")
    def no_coordinate_leak(self) -> DesignPlan:
        text = self.model_dump_json().lower()
        forbidden = [
            "bbox",
            "bounding_box",
            "coordinate",
            "font_size",
            "fold line",
            "x_mm",
            "y_mm",
            "panel dimensions",
        ]
        if any(term in text for term in forbidden):
            raise ValueError("design plan must not include final geometry")
        return self
