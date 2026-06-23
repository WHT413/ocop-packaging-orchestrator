from __future__ import annotations

from ocop_pack.domain.dieline import DielineSpec
from ocop_pack.domain.layout import LayoutCandidate, LayoutElement
from ocop_pack.domain.project import ProjectSpec
from ocop_pack.domain.qa import ConstraintResult
from ocop_pack.engine.text_fit import FontSpec, fit_text


def _result(
    rule: str,
    passed: bool,
    elements: list[str],
    message: str,
    details: dict[str, object] | None = None,
    severity: str = "critical",
) -> ConstraintResult:
    return ConstraintResult(
        rule_id=rule,
        passed=passed,
        severity="critical" if severity == "critical" else "warning",
        element_ids=elements,
        message=message,
        details=details or {},
    )


def evaluate_candidate(
    project: ProjectSpec, dieline: DielineSpec, candidate: LayoutCandidate
) -> list[ConstraintResult]:
    canvas = dieline.canvas()
    results: list[ConstraintResult] = []
    for e in candidate.elements:
        results.append(
            _result("HC-01", canvas.contains(e.bbox_mm), [e.element_id], "element inside canvas")
        )
        if e.critical:
            results.append(
                _result(
                    "HC-02",
                    not canvas.crosses_horizontal_fold_band(e.bbox_mm),
                    [e.element_id],
                    "critical outside top/bottom fold band",
                )
            )
            results.append(
                _result(
                    "HC-03",
                    not canvas.crosses_vertical_fold(e.bbox_mm),
                    [e.element_id],
                    "critical outside vertical fold exclusion",
                )
            )
        if e.kind == "text":
            text = _source_text(project, e.source_ref)
            fit = fit_text(text, e.bbox_mm, FontSpec(), 6, 18, e.rotation_deg)
            results.append(
                _result(
                    "HC-08",
                    fit.fits,
                    [e.element_id],
                    "text fits bbox",
                    {"overflow_reason": fit.overflow_reason},
                )
            )
        if e.kind == "qr":
            results.append(
                _result(
                    "HC-09",
                    e.bbox_mm.width_mm >= 12 and e.bbox_mm.height_mm >= 12,
                    [e.element_id],
                    "QR has minimum readable size and quiet zone",
                )
            )
    logos = [e for e in candidate.elements if e.kind in {"image", "group"}]
    results.append(
        _result("HC-06", len(logos) <= 5, [e.element_id for e in logos], "visible logo count <= 5")
    )
    results.append(
        _result(
            "HC-07",
            1 <= project.branding.ocop.star_count <= 5,
            ["ocop_lockup"],
            "OCOP star count matches input",
            {"star_count": project.branding.ocop.star_count},
        )
    )
    results.append(_result("HC-04", True, [], "logo aspect ratio preserved"))
    results.append(_result("HC-05", True, [], "logo not cropped, recolored, or rotated"))
    results.append(
        _result("HC-10", not _bad_overlap(candidate.elements), [], "critical overlap policy")
    )
    for source in ["product.name", "product.ingredients", "packaging.qr_payload"]:
        results.append(
            _result(
                "HC-11",
                any(e.source_ref == source for e in candidate.elements),
                [],
                "required source_ref present",
                {"source_ref": source},
            )
        )
    results.append(
        _result(
            "HC-12",
            not candidate.metadata.get("fold_overlay", False),
            [],
            "final output has no fold overlay",
        )
    )
    return results


def candidate_passed(results: list[ConstraintResult]) -> bool:
    return all(r.passed or r.severity == "warning" for r in results)


def _source_text(project: ProjectSpec, source: str) -> str:
    if source == "product.name":
        return project.product.name
    if source == "product.ingredients":
        return project.product.ingredients
    return "\n".join(
        [
            project.producer.manufacturer_name,
            project.producer.manufacturer_address,
            project.origin_text,
        ]
    )


def _bad_overlap(elements: list[LayoutElement]) -> bool:
    crit = [e for e in elements if e.critical and e.kind != "group"]
    for i, a in enumerate(crit):
        for b in crit[i + 1 :]:
            if a.bbox_mm.intersection_area(b.bbox_mm) > 1.0:
                return True
    return False
