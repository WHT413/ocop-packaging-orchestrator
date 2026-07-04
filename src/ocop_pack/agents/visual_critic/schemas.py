from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CandidateAestheticScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    readability_hierarchy: float = Field(ge=0, le=10)
    balance_whitespace: float = Field(ge=0, le=10)
    brand_fit: float = Field(ge=0, le=10)
    artwork_relevance: float = Field(ge=0, le=10)
    distinctiveness: float = Field(ge=0, le=10)
    total_score: float = Field(ge=0, le=10)
    summary: str


class TargetedRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artwork_id: str
    issue_code: Literal[
        "BACKGROUND_TOO_BUSY",
        "INSUFFICIENT_NEGATIVE_SPACE",
        "WEAK_VISUAL_FOCUS",
        "LOW_BRAND_FIT",
        "POOR_PANEL_CONTINUITY",
        "ARTWORK_COMPETES_WITH_TEXT",
        "UNBALANCED_VISUAL_WEIGHT",
    ]
    instruction: str
    preserve: list[str]
    prohibited_changes: list[str]


class CriticDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    status: Literal["PASS", "REVISE_ARTWORK", "HUMAN_REVIEW"]
    selected_candidate_id: str | None
    candidate_scores: list[CandidateAestheticScore]
    targeted_revision: TargetedRevision | None
    confidence: float = Field(ge=0, le=1)
    decision_summary: str
