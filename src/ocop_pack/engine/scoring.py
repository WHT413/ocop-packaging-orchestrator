from __future__ import annotations

from ocop_pack.domain.qa import ConstraintResult


def score_results(results: list[ConstraintResult]) -> float:
    return sum(10.0 for r in results if r.passed) - sum(
        100.0 for r in results if not r.passed and r.severity == "critical"
    )
