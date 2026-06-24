from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ArtworkStrategy = Literal[
    "full_bleed_continuous",
    "center_hero",
    "split_botanical",
]


class ArtworkConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_id: str
    description: str
    prompt: str
    negative_prompt: str
    artwork_strategy: ArtworkStrategy

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
    logo_cluster: Literal[
        "top_center",
        "top_split",
        "center_header",
    ]
    side_text_mode: Literal[
        "vertical",
        "horizontal_compact",
        "mixed",
    ]
    artwork_strategy: ArtworkStrategy


class DesignPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "design-plan.v1"
    visual_direction: str
    palette: list[str] = Field(min_length=1, max_length=6)
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
