from __future__ import annotations

from ocop_pack.domain.dieline import DielineSpec
from ocop_pack.domain.geometry import BoundingBox
from ocop_pack.domain.layout import LayoutCandidate, LayoutElement
from ocop_pack.domain.project import ProjectSpec
from ocop_pack.engine.ocop_lockup import compose_ocop_lockup
from ocop_pack.engine.qr import QR_POLICY_VERSION, payload_hash, qr_render_metadata
from ocop_pack.engine.template_registry import TemplateFamily, TemplateRegistry
from ocop_pack.engine.visual_theme import artwork_opacity, resolve_visual_theme, theme_tokens
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
    element_id: str, bbox: BoundingBox, z_index: int, fill: str, opacity: float
) -> LayoutElement:
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
            "corner_radius_mm": 3,
        },
    )


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
    if family.family == "vertical_side_label":
        title_box = _region(center, 0.08, 0.18, 0.84, 0.24)
        logo_box = _region(center, 0.30, 0.08, 0.40, 0.08)
        info_box = _region(center, 0.18, 0.48, 0.64, 0.12)
        left_box = _region(left, 0.22, 0.16, 0.56, 0.70)
        right_box = _region(right, 0.10, 0.12, 0.80, 0.48)
        qr_box = _square_region(right, 0.26, 0.66, 0.48, 0.18)
        side_rotation, right_rotation = 90, 270
    elif family.family == "asymmetric_center_traceability":
        title_box = _region(center, 0.08, 0.18, 0.70, 0.20)
        logo_box = _region(center, 0.54, 0.08, 0.34, 0.09)
        info_box = _region(center, 0.22, 0.50, 0.58, 0.12)
        left_box = _region(left, 0.10, 0.30, 0.78, 0.40)
        right_box = _region(right, 0.10, 0.14, 0.80, 0.32)
        qr_box = _square_region(right, 0.18, 0.43, 0.42, 0.18)
        side_rotation, right_rotation = 0, 0
    else:
        title_box = _region(center, 0.10, 0.23, 0.80, 0.18)
        logo_box = _region(center, 0.25, 0.08, 0.50, 0.10)
        info_box = _region(center, 0.18, 0.45, 0.64, 0.10)
        left_box = _region(left, 0.13, 0.22, 0.74, 0.48)
        right_box = _region(right, 0.13, 0.20, 0.74, 0.34)
        qr_box = _square_region(right, 0.18, 0.59, 0.64, 0.23)
        side_rotation = 90 if intent.side_text_mode in {"vertical", "mixed"} else 0
        right_rotation = side_rotation if side_rotation else 270
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
        _card("title_card", title_box, 20, fill, opacity),
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
        _card("supporting_info_card", info_box, 20, fill, opacity),
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
        _card("left_text_card", left_box, 20, fill, opacity),
        _text(
            "left_text",
            "product.ingredients",
            left_box,
            30,
            "secondary_info",
            "left_secondary",
            3.0,
            "left",
            side_rotation,
            text_color=theme.secondary_text_color,
            font_asset_id=theme.body_font_asset_id,
        ),
        _card("right_text_card", right_box, 20, fill, opacity),
        _text(
            "right_text",
            "producer",
            right_box,
            30,
            "producer_traceability",
            "right_traceability",
            3.0,
            "left",
            right_rotation,
            text_color=theme.secondary_text_color,
            font_asset_id=theme.body_font_asset_id,
        ),
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
