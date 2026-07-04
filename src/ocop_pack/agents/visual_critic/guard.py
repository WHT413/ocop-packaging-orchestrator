from __future__ import annotations

import re
from dataclasses import dataclass

from ocop_pack.agents.visual_critic.schemas import CriticDecision

GEOMETRY_RE = re.compile(
    r"\b(x|y|bbox|width_mm|height_mm|font_size|fold_position|logo_scale|"
    r"qr_position|coordinate|coordinates)\b",
    re.I,
)
TEXT_RE = re.compile(
    r"\b(rewrite|change|edit|modify|translate|replace)\b.*\b(text|claim|copy|words)\b",
    re.I,
)
LOGO_RE = re.compile(
    r"\b(change|edit|modify|replace|redesign)\b.*\b(logo|trademark|ocop)\b",
    re.I,
)
QR_RE = re.compile(r"\b(change|edit|modify|replace|move)\b.*\b(qr|barcode)\b", re.I)
DIELINE_RE = re.compile(r"\b(change|edit|modify|move)\b.*\b(fold|dieline|crease)\b", re.I)
FULL_PACKAGE_RE = re.compile(r"\b(full package|packaging mockup|final label)\b", re.I)


@dataclass(frozen=True)
class CriticGuardContext:
    candidate_ids: set[str]
    artwork_ids: set[str]


class CriticGuardError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_critic_decision(decision: CriticDecision, context: CriticGuardContext) -> None:
    score_ids = {score.candidate_id for score in decision.candidate_scores}
    unknown_selected = (
        decision.selected_candidate_id is not None
        and decision.selected_candidate_id not in context.candidate_ids
    )
    if score_ids - context.candidate_ids or unknown_selected:
        raise CriticGuardError("CRITIC_UNKNOWN_CANDIDATE", "unknown candidate")
    if decision.status == "PASS" and not decision.selected_candidate_id:
        raise CriticGuardError("CRITIC_INVALID_STATUS_COMBINATION", "PASS requires selection")
    if decision.status == "REVISE_ARTWORK" and decision.targeted_revision is None:
        raise CriticGuardError("CRITIC_INVALID_STATUS_COMBINATION", "revision requires target")
    if decision.status != "REVISE_ARTWORK" and decision.targeted_revision is not None:
        raise CriticGuardError("CRITIC_INVALID_STATUS_COMBINATION", "unexpected revision target")
    unknown_artwork = (
        decision.targeted_revision is not None
        and decision.targeted_revision.artwork_id not in context.artwork_ids
    )
    if unknown_artwork:
        raise CriticGuardError("CRITIC_UNBOUNDED_REVISION", "unknown artwork target")
    _reject_forbidden_text(decision.model_dump_json())


def _reject_forbidden_text(text: str) -> None:
    for pattern, code in [
        (GEOMETRY_RE, "CRITIC_COORDINATE_LEAK"),
        (TEXT_RE, "CRITIC_TEXT_CHANGE_REQUEST"),
        (LOGO_RE, "CRITIC_LOGO_CHANGE_REQUEST"),
        (QR_RE, "CRITIC_QR_CHANGE_REQUEST"),
        (DIELINE_RE, "CRITIC_DIELINE_CHANGE_REQUEST"),
        (FULL_PACKAGE_RE, "CRITIC_UNBOUNDED_REVISION"),
    ]:
        if pattern.search(text):
            raise CriticGuardError(code, f"critic output violates guard: {code}")
