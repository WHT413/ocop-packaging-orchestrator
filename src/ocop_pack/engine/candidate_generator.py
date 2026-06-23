from __future__ import annotations

from ocop_pack.domain.dieline import DielineSpec
from ocop_pack.domain.geometry import BoundingBox
from ocop_pack.domain.layout import LayoutCandidate, LayoutElement
from ocop_pack.domain.project import ProjectSpec
from ocop_pack.engine.ocop_lockup import compose_ocop_lockup
from ocop_pack.engine.qr import payload_hash


def _region(panel: BoundingBox, x: float, y: float, w: float, h: float) -> BoundingBox:
    return BoundingBox(
        x_mm=panel.x_mm + panel.width_mm * x,
        y_mm=panel.y_mm + panel.height_mm * y,
        width_mm=panel.width_mm * w,
        height_mm=panel.height_mm * h,
    )


def generate_candidates(
    project: ProjectSpec, dieline: DielineSpec, seed: int = 1
) -> list[LayoutCandidate]:
    panels = {p.name: p.bbox_mm for p in dieline.panels()}
    variants: list[tuple[str, int, float, str, str]] = []
    for template in ["center_focus_vertical_sides_v1", "center_balanced_sides_v1"]:
        for rot in [90, 270] if "focus" in template else [0, 90, 270]:
            for scale in [0.9, 1.0, 1.1]:
                variants.append((template, rot, scale, "top_center", "right_low"))
    candidates: list[LayoutCandidate] = []
    for idx, (template, rot, scale, logo_mode, qr_pos) in enumerate(variants[:18], start=1):
        center, left, right = panels["center_panel"], panels["left_panel"], panels["right_panel"]
        title = _region(center, 0.12, 0.24, 0.76, 0.14 * scale).clamp_to(center)
        logo_box = _region(center, 0.25, 0.09, 0.50, 0.10)
        qr_box = _region(right, 0.28, 0.70, 0.44, 0.12)
        elements = [
            LayoutElement(
                element_id="title",
                kind="text",
                source_ref="product.name",
                bbox_mm=title,
                critical=True,
                z_index=10,
            ),
            LayoutElement(
                element_id="left_text",
                kind="text",
                source_ref="product.ingredients",
                bbox_mm=_region(left, 0.14, 0.20, 0.72, 0.58),
                rotation_deg=rot,
                critical=True,
                z_index=10,
            ),
            LayoutElement(
                element_id="right_text",
                kind="text",
                source_ref="producer",
                bbox_mm=_region(right, 0.14, 0.20, 0.72, 0.38),
                rotation_deg=rot if rot in {90, 270} else 0,
                critical=True,
                z_index=10,
            ),
            LayoutElement(
                element_id="qr",
                kind="qr",
                source_ref="packaging.qr_payload",
                bbox_mm=qr_box,
                critical=True,
                z_index=10,
                metadata={
                    "payload_hash": payload_hash(project.packaging.qr_payload),
                    "quiet_zone": 4,
                },
            ),
            compose_ocop_lockup(
                "branding.ocop.logo_path", project.branding.ocop.star_count, logo_box
            ),
            LayoutElement(
                element_id="background",
                kind="shape",
                source_ref="system.background",
                bbox_mm=BoundingBox(
                    x_mm=0, y_mm=0, width_mm=dieline.width_mm, height_mm=dieline.height_mm
                ),
                z_index=0,
                critical=False,
                metadata={"fill": "#f6f0df" if idx % 2 else "#21312a"},
            ),
        ]
        candidates.append(
            LayoutCandidate(
                candidate_id=f"C{idx:03d}",
                template_id=template,
                seed=seed,
                elements=elements,
                metadata={
                    "logo_cluster_mode": logo_mode,
                    "qr_position": qr_pos,
                    "title_scale": scale,
                },
            )
        )
    return candidates
