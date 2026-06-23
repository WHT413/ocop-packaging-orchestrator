from __future__ import annotations

from pathlib import Path

from ocop_pack.domain.dieline import DielineSpec
from ocop_pack.domain.layout import LayoutCandidate
from ocop_pack.domain.project import ProjectSpec
from ocop_pack.domain.qa import QAReport
from ocop_pack.engine.constraints import candidate_passed, evaluate_candidate
from ocop_pack.engine.qr import decode_qr


def qa_candidate(
    run_id: str,
    project: ProjectSpec,
    dieline: DielineSpec,
    candidate: LayoutCandidate,
    png_path: Path | None = None,
) -> QAReport:
    results = evaluate_candidate(project, dieline, candidate)
    if png_path is not None:
        decoded = decode_qr(png_path)
        for r in results:
            if r.rule_id == "HC-09":
                r.passed = r.passed and decoded == project.packaging.qr_payload
                r.details["decoded_payload"] = decoded
    return QAReport(
        run_id=run_id,
        candidate_id=candidate.candidate_id,
        passed=candidate_passed(results),
        results=results,
    )
