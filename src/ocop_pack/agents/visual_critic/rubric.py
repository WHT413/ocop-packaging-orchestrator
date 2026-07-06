from __future__ import annotations

from typing import Final

from ocop_pack.agents.visual_critic.schemas import CandidateAestheticScore

RUBRIC_VERSION: Final = "critic-rubric.v2"
RUBRIC_WEIGHTS: Final[dict[str, float]] = {
    "readability_hierarchy": 0.30,
    "balance_whitespace": 0.25,
    "brand_fit": 0.20,
    "artwork_relevance": 0.15,
    "distinctiveness": 0.10,
}


def weighted_total(score: CandidateAestheticScore) -> float:
    return round(
        score.readability_hierarchy * RUBRIC_WEIGHTS["readability_hierarchy"]
        + score.balance_whitespace * RUBRIC_WEIGHTS["balance_whitespace"]
        + score.brand_fit * RUBRIC_WEIGHTS["brand_fit"]
        + score.artwork_relevance * RUBRIC_WEIGHTS["artwork_relevance"]
        + score.distinctiveness * RUBRIC_WEIGHTS["distinctiveness"],
        2,
    )
