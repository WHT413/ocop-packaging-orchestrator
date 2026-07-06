from __future__ import annotations

from ocop_pack.domain.dieline import DielineSpec
from ocop_pack.domain.geometry import BoundingBox
from ocop_pack.domain.layout import LayoutCandidate, LayoutElement
from ocop_pack.domain.project import ProjectSpec
from ocop_pack.engine.barcode import ean13_modules
from ocop_pack.engine.ocop_lockup import compose_ocop_lockup
from ocop_pack.engine.qr import QR_POLICY_VERSION, payload_hash, qr_render_metadata
from ocop_pack.engine.template_registry import TemplateFamily, TemplateRegistry
from ocop_pack.engine.visual_theme import (
    VisualTheme,
    artwork_opacity,
    resolve_visual_theme,
    theme_tokens,
)
from ocop_pack.schemas.design_planner import DesignPlan, LayoutIntent


def _region(panel: BoundingBox, x: float, y: float, w: float, h: float) -> BoundingBox:
    return BoundingBox(
        x_mm=panel.x_mm + panel.width_mm * x,
        y_mm=panel.y_mm + panel.height_mm * y,
        width_mm=panel.width_mm * w,
        height_mm=panel.height_mm * h,
    )


def _square_region(panel: BoundingBox, x: float, y: float, w: float, h: float) -> BoundingBox:
    region = _region(panel, x, y, w, h)
    side = min(region.width_mm, region.height_mm)
    return BoundingBox(
        x_mm=region.x_mm + (region.width_mm - side) / 2,
        y_mm=region.y_mm + (region.height_mm - side) / 2,
        width_mm=side,
        height_mm=side,
    )


def _card(
    element_id: str,
    bbox: BoundingBox,
    z_index: int,
    fill: str,
    opacity: float,
    radius_mm: float = 3,
    frame_style: str = "paper_label",
    badge_motif: str | None = None,
) -> LayoutElement:
    shape_style = _element_frame_style(element_id, frame_style)
    return LayoutElement(
        element_id=element_id,
        kind="shape",
        source_ref="system.readability_guard",
        bbox_mm=bbox,
        z_index=z_index,
        metadata={
            "fill": fill,
            "opacity": opacity,
            "border_color": fill,
            "role": "readability_guard",
            "corner_radius_mm": radius_mm,
            "frame_style": shape_style,
            "badge_motif": badge_motif or "",
        },
    )


def _with_border(card: LayoutElement, color: str, width_mm: float) -> LayoutElement:
    return card.model_copy(
        update={
            "metadata": {
                **card.metadata,
                "border_color": color,
                "border_width_mm": width_mm,
            }
        }
    )


def _element_frame_style(element_id: str, frame_style: str) -> str:
    if frame_style != "natural_reference_mix":
        return frame_style
    if element_id == "left_text_card":
        return "leaf_badge"
    if element_id == "right_text_card":
        return "woven_label"
    if element_id in {"details_text_card", "nutrition_text_card"}:
        return "torn_paper"
    if element_id == "supporting_info_card":
        return "vellum_overlay"
    if element_id == "title_card":
        return "soft_scrim"
    return "paper_label"


def _net_content_badge_motif(project: ProjectSpec) -> str:
    text = f"{project.product.name} {project.product.category}".lower()
    if any(token in text for token in ["ca phe", "coffee", "cafe"]):
        return "coffee_bean"
    if any(token in text for token in ["sen", "lotus"]):
        return "lotus_seed"
    if any(token in text for token in ["mat ong", "honey"]):
        return "honey_drop"
    if any(token in text for token in ["chuoi", "banana"]):
        return "banana_slice"
    if any(token in text for token in ["dau tam", "berry", "mut"]):
        return "berry"
    return "leaf"


def _choose(value: str, allowed: tuple[str, ...], seed: int, idx: int) -> str:
    if value != "theme_default":
        return value
    return allowed[(seed + idx - 1) % len(allowed)]


def _style_controls(
    intent: LayoutIntent, seed: int, idx: int, fill: str, secondary_fill: str, opacity: float
) -> dict[str, object]:
    frame_style = _choose(
        intent.frame_style,
        (
            "paper_label",
            "soft_scrim",
            "kraft_card",
            "premium_badge",
            "torn_paper",
            "leaf_badge",
            "woven_label",
            "vellum_overlay",
            "brush_stroke",
            "natural_reference_mix",
        ),
        seed,
        idx,
    )
    font_mood = _choose(
        intent.font_mood,
        ("refined_natural", "artisanal_bold", "functional_safe"),
        seed // 3,
        idx,
    )
    contrast_style = _choose(
        intent.contrast_style,
        ("balanced_scrim", "light_scrim", "opaque_card"),
        seed // 7,
        idx,
    )
    frame = {
        "paper_label": (fill, 3.0),
        "soft_scrim": (secondary_fill, 5.0),
        "kraft_card": (secondary_fill, 2.0),
        "premium_badge": (fill, 6.0),
        "torn_paper": (fill, 1.0),
        "leaf_badge": (secondary_fill, 8.0),
        "woven_label": (fill, 1.5),
        "vellum_overlay": (fill, 4.0),
        "brush_stroke": (secondary_fill, 6.0),
        "natural_reference_mix": (fill, 3.0),
    }[frame_style]
    contrast = {
        "light_scrim": max(0.18, opacity - 0.42),
        "balanced_scrim": max(0.36, opacity - 0.22),
        "opaque_card": max(0.86, opacity),
    }[contrast_style]
    return {
        "frame_style": frame_style,
        "font_mood": font_mood,
        "contrast_style": contrast_style,
        "fill": frame[0],
        "opacity": contrast,
        "radius_mm": frame[1],
    }


def _retail_surface(
    project: ProjectSpec, intent: LayoutIntent, theme: VisualTheme
) -> dict[str, object]:
    safe_styles = {"paper_label", "soft_scrim", "kraft_card", "vellum_overlay"}
    if intent.frame_style in safe_styles:
        frame_style = intent.frame_style
    else:
        text = " ".join(
            [project.product.name, project.product.category, project.creative_brief_raw]
        ).lower()
        if any(token in text for token in ["ca phe", "coffee", "cafe"]):
            frame_style = "kraft_card"
        elif any(token in text for token in ["tra", "tea", "matcha", "botanical"]):
            frame_style = "vellum_overlay"
        elif any(token in text for token in ["mat ong", "honey"]):
            frame_style = "soft_scrim"
        else:
            frame_style = "paper_label"
    look = {
        "kraft_card": (theme.card_secondary_fill, 0.48, 2.0),
        "vellum_overlay": (theme.card_fill, 0.40, 3.0),
        "soft_scrim": (theme.card_fill, 0.36, 3.5),
        "paper_label": (theme.card_fill, 0.46, 2.2),
    }[frame_style]
    return {"frame_style": frame_style, "fill": look[0], "opacity": look[1], "radius_mm": look[2]}


def _barcode_bars(seed: str, bbox: BoundingBox, fill: str) -> list[LayoutElement]:
    bars: list[LayoutElement] = []
    modules = ean13_modules(seed)
    module_w = bbox.width_mm / len(modules)
    for idx, bit in enumerate(modules):
        if bit != "1":
            continue
        bars.append(
            LayoutElement(
                element_id=f"barcode_bar_{idx:02d}",
                kind="shape",
                source_ref="packaging.barcode",
                bbox_mm=BoundingBox(
                    x_mm=bbox.x_mm + idx * module_w,
                    y_mm=bbox.y_mm,
                    width_mm=module_w * 0.96,
                    height_mm=bbox.height_mm,
                ),
                z_index=31,
                metadata={
                    "fill": fill,
                    "opacity": 1.0,
                    "border_color": fill,
                    "role": "barcode_bar",
                    "corner_radius_mm": 0,
                },
            )
        )
    return bars


def _traceability_elements(
    project: ProjectSpec, qr_box: BoundingBox, barcode_box: BoundingBox
) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    if project.packaging.show_qr:
        elements.extend(
            [
                _card("qr_card", qr_box, 20, "#ffffff", 1.0),
                LayoutElement(
                    element_id="qr",
                    kind="qr",
                    source_ref="packaging.qr_payload",
                    bbox_mm=qr_box,
                    critical=True,
                    z_index=30,
                    metadata={
                        "payload_hash": payload_hash(project.packaging.qr_payload),
                        "quiet_zone": 4,
                        "qr_policy_version": QR_POLICY_VERSION,
                        **qr_render_metadata(project.packaging.qr_payload, qr_box),
                        "role": "traceability",
                        "panel_role": "right_traceability",
                        "guard_id": "qr_card",
                        "padding_mm": 3,
                    },
                ),
            ]
        )
    if project.packaging.show_barcode:
        bars_box = BoundingBox(
            x_mm=barcode_box.x_mm + barcode_box.width_mm * 0.06,
            y_mm=barcode_box.y_mm + barcode_box.height_mm * 0.08,
            width_mm=barcode_box.width_mm * 0.88,
            height_mm=barcode_box.height_mm * 0.84,
        )
        elements.append(_card("barcode_card", barcode_box, 20, "#ffffff", 1.0, 1.2))
        elements.extend(_barcode_bars(project.project_id, bars_box, "#111111"))
    return elements


def _text(
    element_id: str,
    source_ref: str,
    bbox: BoundingBox,
    z_index: int,
    role: str,
    panel_role: str,
    font_mm: float,
    align: str = "left",
    rotation_deg: int = 0,
    text_color: str = "#111111",
    font_asset_id: str = "noto-sans-regular",
) -> LayoutElement:
    return LayoutElement(
        element_id=element_id,
        kind="text",
        source_ref=source_ref,
        bbox_mm=bbox,
        rotation_deg=rotation_deg,
        critical=True,
        z_index=z_index,
        metadata={
            "role": role,
            "panel_role": panel_role,
            "font_size_mm": font_mm,
            "align": align,
            "text_color": text_color,
            "font_asset_id": font_asset_id,
            "padding_mm": 3,
            "requires_readability_guard": True,
            "guard_id": f"{element_id}_card",
        },
    )


def _default_plan() -> DesignPlan:
    return DesignPlan.model_validate(
        {
            "visual_direction": "clean botanical premium OCOP packaging",
            "palette": ["tea green", "warm ivory", "deep leaf"],
            "decorative_motifs": ["regional botanical texture"],
            "artwork_density": "balanced",
            "negative_space_intent": "balanced",
            "creative_assumptions": ["fallback deterministic plan"],
            "conflicts_or_unsupported_preferences": [],
            "artwork_concepts": [
                {
                    "concept_id": "A01",
                    "description": "Decorative botanical texture.",
                    "prompt": "decorative botanical texture",
                    "negative_prompt": "no letters, no numbers, no marks",
                    "artwork_strategy": "softened_full_background",
                }
            ],
            "layout_intents": [
                {
                    "panel_strategy": "center_lockup_balanced_sides",
                    "side_text_mode": "mixed",
                    "artwork_strategy": "softened_full_background",
                    "panel_roles": "center_primary_left_info_right_traceability",
                    "content_hierarchy": "title_first",
                    "title_block_intent": "hero_label_card",
                    "info_block_intent": "side_label_cards",
                    "protected_zone_strategy": "guard_all_critical_text",
                    "contrast_strategy": "semi_opaque_warm_scrims",
                }
            ],
            "prohibited_content": [],
            "rationale": "fallback deterministic plan",
        }
    )


def generate_candidates(
    project: ProjectSpec,
    dieline: DielineSpec,
    seed: int = 1,
    design_plan: DesignPlan | None = None,
) -> list[LayoutCandidate]:
    plan = design_plan or _default_plan()
    panels = {p.name: p.bbox_mm for p in dieline.panels()}
    registry = TemplateRegistry()
    variants: list[tuple[LayoutIntent, TemplateFamily]] = []
    for intent in plan.layout_intents:
        variants.extend((intent, family) for family in registry.eligible(plan, intent))
    seen = {family.family for _, family in variants}
    if len(seen) < min(3, len(registry.all())):
        variants.extend(
            (plan.layout_intents[0], family)
            for family in registry.all()
            if family.family not in seen
        )

    candidates: list[LayoutCandidate] = []
    for idx, (intent, family) in enumerate(variants[:6], start=1):
        candidates.append(
            _build_candidate(project, dieline, panels, plan, intent, family, seed, idx)
        )
    return candidates


def _build_candidate(
    project: ProjectSpec,
    dieline: DielineSpec,
    panels: dict[str, BoundingBox],
    plan: DesignPlan,
    intent: LayoutIntent,
    family: TemplateFamily,
    seed: int,
    idx: int,
) -> LayoutCandidate:
    center, left, right = panels["center_panel"], panels["left_panel"], panels["right_panel"]
    theme, theme_diagnostics = resolve_visual_theme(project, plan, intent)
    fill = (
        theme.card_fill
        if intent.contrast_strategy == "opaque_light_cards"
        else theme.card_secondary_fill
    )
    opacity = (
        max(theme.card_opacity, 0.96)
        if intent.contrast_strategy == "opaque_light_cards"
        else theme.card_opacity
    )
    style = _style_controls(intent, seed, idx, fill, theme.card_secondary_fill, opacity)
    fill = str(style["fill"])
    opacity = float(style["opacity"])
    radius_mm = float(style["radius_mm"])
    if family.family == "retail_label_reference":
        title_box = _region(center, 0.05, 0.16, 0.90, 0.20)
        logo_box = _region(center, 0.33, 0.075, 0.34, 0.08)
        info_box = _region(center, 0.24, 0.41, 0.52, 0.09)
        left_box = _region(left, 0.18, 0.805, 0.60, 0.072)
        right_box = _region(right, 0.09, 0.19, 0.82, 0.145)
        qr_box = _square_region(right, 0.22, 0.595, 0.56, 0.16)
        side_rotation, right_rotation = 0, 0
    elif family.family == "vertical_side_label":
        title_box = _region(center, 0.08, 0.17, 0.84, 0.23)
        logo_box = _region(center, 0.31, 0.06, 0.38, 0.10)
        info_box = _region(center, 0.21, 0.44, 0.58, 0.12)
        left_box = _region(left, 0.10, 0.18, 0.80, 0.14)
        right_box = _region(right, 0.08, 0.17, 0.84, 0.23)
        qr_box = _square_region(right, 0.20, 0.56, 0.60, 0.17)
        side_rotation, right_rotation = 0, 0
    elif family.family == "asymmetric_center_traceability":
        title_box = _region(center, 0.07, 0.18, 0.80, 0.22)
        logo_box = _region(center, 0.51, 0.06, 0.38, 0.10)
        info_box = _region(center, 0.20, 0.44, 0.58, 0.12)
        left_box = _region(left, 0.10, 0.18, 0.80, 0.14)
        right_box = _region(right, 0.08, 0.18, 0.84, 0.23)
        qr_box = _square_region(right, 0.20, 0.57, 0.60, 0.17)
        side_rotation, right_rotation = 0, 0
    else:
        title_box = _region(center, 0.08, 0.18, 0.84, 0.22)
        logo_box = _region(center, 0.31, 0.06, 0.38, 0.10)
        info_box = _region(center, 0.21, 0.44, 0.58, 0.12)
        left_box = _region(left, 0.10, 0.18, 0.80, 0.14)
        right_box = _region(right, 0.08, 0.18, 0.84, 0.23)
        qr_box = _square_region(right, 0.20, 0.57, 0.60, 0.17)
        side_rotation, right_rotation = 0, 0
    if family.family == "retail_label_reference":
        info_panel_box = _region(center, 0.06, 0.57, 0.88, 0.23)
        details_box = _region(center, 0.10, 0.60, 0.43, 0.17)
        nutrition_box = _region(center, 0.532, 0.60, 0.43, 0.17)
        barcode_box = _region(right, 0.24, 0.735, 0.52, 0.10)
    else:
        info_panel_box = _region(center, 0.06, 0.61, 0.88, 0.24)
        details_box = _region(center, 0.09, 0.64, 0.39, 0.17)
        nutrition_box = _region(center, 0.54, 0.64, 0.35, 0.17)
        barcode_box = _region(right, 0.22, 0.745, 0.56, 0.10)
    is_retail_reference = family.family == "retail_label_reference"
    title_card_opacity = 0.06 if is_retail_reference else opacity
    supporting_card_opacity = 0.34 if is_retail_reference else opacity
    side_card_opacity = 0.42 if is_retail_reference else opacity
    info_card_opacity = 0.50 if is_retail_reference else opacity
    retail_surface = _retail_surface(project, intent, theme)
    retail_card_fill = str(retail_surface["fill"]) if is_retail_reference else fill
    retail_card_radius = float(retail_surface["radius_mm"]) if is_retail_reference else radius_mm
    retail_card_frame = (
        str(retail_surface["frame_style"]) if is_retail_reference else str(style["frame_style"])
    )
    if is_retail_reference:
        supporting_card_opacity = float(retail_surface["opacity"]) * 0.8
        side_card_opacity = float(retail_surface["opacity"]) * 0.95
        info_card_opacity = float(retail_surface["opacity"])
    footer_fill = theme.accent_color
    footer_opacity = 0.82 if is_retail_reference else 0.75
    footer_text_color = "#fff5c8" if is_retail_reference else theme.primary_text_color
    lockup = compose_ocop_lockup(
        "branding.ocop.logo_path", project.branding.ocop.star_count, logo_box
    )
    lockup = lockup.model_copy(
        update={
            "z_index": 31,
            "metadata": {**lockup.metadata, "role": "ocop_lockup", "panel_role": "center_primary"},
        }
    )
    elements: list[LayoutElement] = [
        LayoutElement(
            element_id="background",
            kind="shape",
            source_ref="system.background",
            bbox_mm=BoundingBox(
                x_mm=0, y_mm=0, width_mm=dieline.width_mm, height_mm=dieline.height_mm
            ),
            z_index=0,
            metadata={
                "fill": theme.background_color,
                "role": "base_background",
                "visual_theme_token": "background_color",
            },
        ),
        LayoutElement(
            element_id="footer_text_card",
            kind="shape",
            source_ref="system.readability_guard",
            bbox_mm=BoundingBox(
                x_mm=0,
                y_mm=dieline.height_mm * 0.895,
                width_mm=dieline.width_mm,
                height_mm=dieline.height_mm * 0.07,
            ),
            z_index=12,
            metadata={
                "fill": footer_fill,
                "opacity": footer_opacity,
                "border_color": footer_fill,
                "role": "decorative_footer",
                "corner_radius_mm": 0,
            },
        ),
        LayoutElement(
            element_id="footer_text",
            kind="text",
            source_ref="origin_text",
            bbox_mm=BoundingBox(
                x_mm=0,
                y_mm=dieline.height_mm * 0.895,
                width_mm=dieline.width_mm,
                height_mm=dieline.height_mm * 0.07,
            ),
            z_index=30,
            metadata={
                "role": "footer",
                "panel_role": "decorative_footer",
                "align": "center",
                "text_color": footer_text_color,
                "font_asset_id": theme.body_font_asset_id,
                "padding_mm": 2,
            },
        ),
        _card(
            "title_card",
            title_box,
            20,
            fill,
            title_card_opacity,
            radius_mm,
            str(style["frame_style"]),
        ),
        _text(
            "title",
            "product.name",
            title_box,
            30,
            "title",
            "center_primary",
            8.0,
            "center",
            text_color=theme.primary_text_color,
            font_asset_id=theme.title_font_asset_id,
        ),
        lockup,
        _card(
            "supporting_info_card",
            info_box,
            20,
            retail_card_fill,
            supporting_card_opacity,
            retail_card_radius,
            retail_card_frame,
        ),
        _text(
            "supporting_info",
            "product.category",
            info_box,
            30,
            "product_subtitle",
            "center_primary",
            3.2,
            "center",
            text_color=theme.secondary_text_color,
            font_asset_id=theme.subtitle_font_asset_id,
        ),
        _card(
            "left_text_card",
            left_box,
            20,
            retail_card_fill,
            0.34 if is_retail_reference else side_card_opacity,
            2.2,
            "paper_label",
        ),
        _text(
            "left_text",
            "product.net_content",
            left_box,
            30,
            "short_claim",
            "left_secondary",
            3.8,
            "center",
            side_rotation,
            text_color=theme.secondary_text_color,
            font_asset_id=theme.subtitle_font_asset_id,
        ),
        _card(
            "right_text_card",
            right_box,
            20,
            retail_card_fill,
            side_card_opacity,
            retail_card_radius,
            retail_card_frame,
        ),
        _text(
            "right_text",
            "producer.short",
            right_box,
            30,
            "traceability",
            "right_traceability",
            3.0,
            "center",
            right_rotation,
            text_color=theme.secondary_text_color,
            font_asset_id=theme.body_font_asset_id,
        ),
        _card(
            "details_text_card",
            info_panel_box,
            20,
            retail_card_fill,
            info_card_opacity,
            retail_card_radius,
            retail_card_frame,
        ),
        _text(
            "details_text",
            "product.details",
            details_box,
            30,
            "dense_info",
            "center_primary",
            2.0,
            "left",
            text_color=theme.secondary_text_color,
            font_asset_id=theme.body_font_asset_id,
        ),
        _card(
            "nutrition_text_card",
            info_panel_box,
            20,
            retail_card_fill,
            info_card_opacity,
            retail_card_radius,
            retail_card_frame,
        ),
        _text(
            "nutrition_text",
            "product.nutrition",
            nutrition_box,
            30,
            "dense_info",
            "center_primary",
            2.0,
            "left",
            text_color=theme.secondary_text_color,
            font_asset_id=theme.body_font_asset_id,
        ),
        *_traceability_elements(project, qr_box, barcode_box),
    ]
    topology_signature = [
        (
            e.element_id,
            e.kind,
            e.source_ref,
            e.rotation_deg,
            e.metadata.get("panel_role"),
            round(e.bbox_mm.x_mm, 2),
            round(e.bbox_mm.y_mm, 2),
            round(e.bbox_mm.width_mm, 2),
            round(e.bbox_mm.height_mm, 2),
        )
        for e in elements
    ]
    return LayoutCandidate(
        candidate_id=f"C{idx:03d}",
        template_id=family.template_id,
        seed=seed,
        elements=elements,
        metadata={
            "planner_intent": intent.model_dump(mode="json"),
            "panel_roles": intent.panel_roles,
            "content_hierarchy": intent.content_hierarchy,
            "title_block_intent": intent.title_block_intent,
            "info_block_intent": intent.info_block_intent,
            "protected_zone_strategy": intent.protected_zone_strategy,
            "contrast_strategy": intent.contrast_strategy,
            "frame_style": style["frame_style"],
            "font_mood": style["font_mood"],
            "contrast_style": style["contrast_style"],
            "retail_surface": retail_surface,
            "artwork_mode": intent.artwork_strategy,
            "template_family": family.family,
            "template_config_version": family.version,
            "template_topology": list(family.topology),
            "slot_ownership": family.slot_ownership,
            "hierarchy": list(family.hierarchy),
            "topology_signature": topology_signature,
            "planner_strategy_consumed_by": "template_family_selection",
            "visual_theme": {"theme_id": theme.theme_id, **theme_tokens(theme)},
            "visual_theme_diagnostics": {
                **theme_diagnostics,
                "candidate_elements": [e.element_id for e in elements],
            },
            "structure_variant": family.family,
        },
    )


def _artwork_box(candidate: LayoutCandidate, mode: str, background: LayoutElement) -> BoundingBox:
    if mode == "softened_full_background":
        return background.bbox_mm
    title = next(e for e in candidate.elements if e.element_id == "title")
    if mode == "framed_hero_region":
        return BoundingBox(
            x_mm=title.bbox_mm.x_mm,
            y_mm=title.bbox_mm.bottom + 4,
            width_mm=title.bbox_mm.width_mm,
            height_mm=title.bbox_mm.height_mm * 1.35,
        )
    left = next(e for e in candidate.elements if e.element_id == "left_text")
    return BoundingBox(
        x_mm=left.bbox_mm.x_mm,
        y_mm=left.bbox_mm.bottom + 4,
        width_mm=left.bbox_mm.width_mm,
        height_mm=max(8, left.bbox_mm.height_mm * 0.22),
    )


def attach_artwork_layers(
    candidates: list[LayoutCandidate], artwork_refs: dict[str, str], artwork_hashes: dict[str, str]
) -> list[LayoutCandidate]:
    if not artwork_refs:
        return candidates
    artwork_ids = sorted(artwork_refs)
    decorated: list[LayoutCandidate] = []
    for index, candidate in enumerate(candidates):
        theme_data = candidate.metadata.get("visual_theme", {})
        mode = str(candidate.metadata.get("artwork_mode", "softened_full_background"))
        if mode not in {
            "softened_full_background",
            "framed_hero_region",
            "panel_local_decorative_strip",
        }:
            decorated.append(
                candidate.model_copy(
                    update={"metadata": {**candidate.metadata, "unsupported_artwork_mode": mode}}
                )
            )
            continue
        artwork_id = artwork_ids[index % len(artwork_ids)]
        background = next(e for e in candidate.elements if e.element_id == "background")
        opacity = 0.72
        if isinstance(theme_data, dict):
            from ocop_pack.engine.visual_theme import THEMES

            theme = THEMES.get(str(theme_data.get("theme_id", "")))
            if theme:
                presence = str(
                    candidate.metadata.get("visual_theme_diagnostics", {})
                    .get("planner_intent", {})
                    .get("artwork_presence", "balanced")
                )
                opacity = artwork_opacity(theme, mode, presence, mode == "softened_full_background")
        elements = list(candidate.elements)
        elements.append(
            LayoutElement(
                element_id="artwork_layer",
                kind="image",
                source_ref=f"artwork:{artwork_id}",
                bbox_mm=_artwork_box(candidate, mode, background).clamp_to(background.bbox_mm),
                z_index=5,
                metadata={
                    "fit": "contain" if mode == "framed_hero_region" else "cover",
                    "opacity": opacity,
                    "artwork_hash": artwork_hashes.get(artwork_id, ""),
                    "artwork_mode": mode,
                    "decorative_only": True,
                },
            )
        )
        metadata = {
            **candidate.metadata,
            "artwork_id": artwork_id,
            "artwork_ref": artwork_refs[artwork_id],
            "artwork_hash": artwork_hashes.get(artwork_id, ""),
            "artwork_mode": mode,
        }
        decorated.append(candidate.model_copy(update={"elements": elements, "metadata": metadata}))
    return decorated
