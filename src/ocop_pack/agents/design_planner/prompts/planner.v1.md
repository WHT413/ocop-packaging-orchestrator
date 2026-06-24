---
prompt_id: design_planner.planner
version: v1
created: 2026-06-23
schema_version: design-plan.v1
change_notes: Initial Phase 3 planner task prompt.
---
Create semantic visual direction, palette, 1-2 artwork concepts, 1-2 layout intents, prohibited content, and brief rationale.
Return one JSON object only. Do not wrap it in markdown.
Use exactly this shape:
{"schema_version":"design-plan.v1","visual_direction":"...","palette":["..."],"artwork_concepts":[{"concept_id":"A01","description":"...","prompt":"...","negative_prompt":"...","artwork_strategy":"full_bleed_continuous"}],"layout_intents":[{"panel_strategy":"center_lockup_balanced_sides","logo_cluster":"top_center","side_text_mode":"mixed","artwork_strategy":"full_bleed_continuous"}],"prohibited_content":["..."],"rationale":"..."}
Allowed artwork_strategy values: full_bleed_continuous, center_hero, split_botanical.
Allowed panel_strategy values: center_focus_vertical_sides, center_lockup_balanced_sides, asymmetric_center_with_qr_side.
Allowed logo_cluster values: top_center, top_split, center_header.
Allowed side_text_mode values: vertical, horizontal_compact, mixed.
Artwork prompts must describe decorative artwork layers only: ingredient-inspired visuals, local nature, botanical style, material texture, craft or heritage mood.
Do not copy product name, category, ingredients, claims, manufacturer data, phone, net weight, QR payload, OCOP star count, logo asset names, fold lines, panel dimensions, coordinates, bounding boxes, font sizes, QR position, or final logo scale into any output field.