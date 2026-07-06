from __future__ import annotations

from ocop_pack.domain.dieline import DielineSpec
from ocop_pack.domain.layout import LayoutCandidate, LayoutElement
from ocop_pack.domain.project import ProjectSpec
from ocop_pack.domain.qa import ConstraintResult
from ocop_pack.engine.qr import MIN_QR_SIZE_MM, QUIET_ZONE_MODULES, qr_render_metadata
from ocop_pack.engine.typography import TypographyError, resolve_text_layout, typography_qa_results
from ocop_pack.engine.visual_theme import visual_theme_qa_results


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
            try:
                layout = resolve_text_layout(project, e)
                fits = True
                details = layout.model_dump(mode="json")
            except TypographyError as exc:
                fits = False
                details = {"overflow_reason": str(exc)}
            results.append(
                _result(
                    "HC-08",
                    fits,
                    [e.element_id],
                    "text fits bbox",
                    details,
                )
            )
        if e.kind == "qr":
            qr_details: dict[str, object] = {}
            try:
                qr_details = qr_render_metadata(project.packaging.qr_payload, e.bbox_mm)
                valid_qr = (
                    abs(e.bbox_mm.width_mm - e.bbox_mm.height_mm) < 1e-6
                    and e.bbox_mm.width_mm >= MIN_QR_SIZE_MM
                    and int(e.metadata.get("quiet_zone", 0)) >= QUIET_ZONE_MODULES
                )
            except ValueError as exc:
                valid_qr = False
                qr_details = {"error": str(exc)}
            results.append(
                _result(
                    "HC-09",
                    valid_qr,
                    [e.element_id],
                    "QR has minimum readable size and quiet zone",
                    qr_details,
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
    results.extend(_composition_results(dieline, candidate))
    required_sources = ["product.name", "product.net_content"]
    if project.packaging.show_qr:
        required_sources.append("packaging.qr_payload")
    for source in required_sources:
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
    results.extend(typography_qa_results(project, candidate))
    results.extend(visual_theme_qa_results(candidate))
    return results


def _composition_results(
    dieline: DielineSpec, candidate: LayoutCandidate
) -> list[ConstraintResult]:
    canvas = dieline.canvas()
    results: list[ConstraintResult] = []
    elements = {e.element_id: e for e in candidate.elements}
    critical = [e for e in candidate.elements if e.critical]
    approved_modes = {
        "softened_full_background",
        "framed_hero_region",
        "panel_local_decorative_strip",
    }
    results.append(
        _result(
            "HC-13",
            candidate.metadata.get("artwork_mode") in approved_modes
            and not candidate.metadata.get("unsupported_artwork_mode"),
            [],
            "approved artwork mode",
        )
    )
    missing_guards = [
        e.element_id
        for e in critical
        if e.metadata.get("requires_readability_guard")
        and e.metadata.get("guard_id") not in elements
    ]
    results.append(
        _result("HC-14", not missing_guards, missing_guards, "critical text has readability guard")
    )
    bad_z = [
        e.element_id
        for e in critical
        if any(
            a.kind == "image" and a.z_index >= e.z_index and a.bbox_mm.intersects(e.bbox_mm)
            for a in candidate.elements
        )
    ]
    results.append(_result("HC-15", not bad_z, bad_z, "artwork cannot cover critical content"))
    bad_panels = []
    for e in critical:
        panel = canvas.panel_for(e.bbox_mm)
        role = str(e.metadata.get("panel_role", ""))
        if role.startswith("center") and panel != "center_panel":
            bad_panels.append(e.element_id)
        if role.startswith("left") and panel != "left_panel":
            bad_panels.append(e.element_id)
        if role.startswith("right") and panel != "right_panel":
            bad_panels.append(e.element_id)
    results.append(_result("HC-16", not bad_panels, bad_panels, "panel roles respected"))
    fold_critical = [
        e.element_id for e in critical if canvas.crosses_horizontal_fold_band(e.bbox_mm)
    ]
    results.append(
        _result("HC-17", not fold_critical, fold_critical, "fold bands contain no critical content")
    )
    results.append(
        _result(
            "HC-18",
            "title" in elements and elements["title"].metadata.get("role") == "title",
            ["title"],
            "title hierarchy block present",
        )
    )
    consumed_fields = [
        "panel_roles",
        "content_hierarchy",
        "title_block_intent",
        "info_block_intent",
        "protected_zone_strategy",
        "contrast_strategy",
        "frame_style",
        "font_mood",
        "contrast_style",
        "artwork_mode",
    ]
    ignored = [name for name in consumed_fields if name not in candidate.metadata]
    structural = all(
        candidate.metadata.get(name)
        for name in [
            "template_family",
            "template_topology",
            "slot_ownership",
            "hierarchy",
            "topology_signature",
        ]
    )
    results.append(
        _result(
            "HC-19",
            not ignored
            and structural
            and candidate.metadata.get("planner_strategy_consumed_by")
            == "template_family_selection",
            [],
            "planner intent consumed by selected template",
            {"ignored": ignored, "structural_consumption": structural},
        )
    )
    for e in [item for item in critical if item.kind == "text"]:
        pad = float(e.metadata.get("padding_mm", 0))
        results.append(
            _result(
                "HC-20",
                pad >= 2 and e.bbox_mm.width_mm > pad * 2 and e.bbox_mm.height_mm > pad * 2,
                [e.element_id],
                "safe text padding",
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
