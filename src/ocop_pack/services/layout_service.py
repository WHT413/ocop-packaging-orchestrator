from __future__ import annotations

from ocop_pack.domain.dieline import DielineSpec
from ocop_pack.domain.layout import LayoutCandidate
from ocop_pack.domain.project import ProjectSpec
from ocop_pack.engine.candidate_generator import generate_candidates
from ocop_pack.engine.constraints import candidate_passed, evaluate_candidate


def generate_valid_candidates(
    project: ProjectSpec, dieline: DielineSpec, seed: int = 1
) -> list[LayoutCandidate]:
    return [
        c
        for c in generate_candidates(project, dieline, seed)
        if candidate_passed(evaluate_candidate(project, dieline, c))
    ]
