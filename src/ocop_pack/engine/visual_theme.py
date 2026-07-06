from __future__ import annotations

from dataclasses import dataclass

from ocop_pack.domain.layout import LayoutCandidate
from ocop_pack.domain.project import ProjectSpec
from ocop_pack.domain.qa import ConstraintResult
from ocop_pack.schemas.design_planner import DesignPlan, LayoutIntent


class VisualThemeError(RuntimeError):
    pass


@dataclass(frozen=True)
class VisualTheme:
    theme_id: str
    background_color: str
    card_fill: str
    card_secondary_fill: str
    primary_text_color: str
    secondary_text_color: str
    accent_color: str
    border_color: str
    title_font_asset_id: str
    subtitle_font_asset_id: str
    body_font_asset_id: str
    artwork_mode: str
    artwork_opacity_range: tuple[float, float]
    card_opacity: float
    texture_tokens: tuple[str, ...] = ()
    accent_tokens: tuple[str, ...] = ()


SUPPORTED_TYPOGRAPHY_MOODS = {"artisanal_serif", "refined_natural", "functional_safe"}
SUPPORTED_PALETTE_MOODS = {"honey_warm", "matcha_cool", "coffee_roast", "lotus_premium"}
SUPPORTED_ARTWORK_PRESENCE = {"soft", "balanced", "rich"}
SUPPORTED_CARD_STYLES = {"cream_gold", "calm_sage", "kraft_coffee", "lotus_paper"}
DISPLAY_ROLES = {"product_title", "product_subtitle", "short_claim", "title"}
FUNCTIONAL_FONT_ASSET_ID = "noto-sans-regular"
DISPLAY_FONT_ASSET_ID = "noto-sans-bold"


THEMES: dict[str, VisualTheme] = {
    "honey_artisanal": VisualTheme(
        theme_id="honey_artisanal",
        background_color="#fff4da",
        card_fill="#fff8e8",
        card_secondary_fill="#fff1c7",
        primary_text_color="#5a2f0f",
        secondary_text_color="#704414",
        accent_color="#c87a12",
        border_color="#d6a13a",
        title_font_asset_id=DISPLAY_FONT_ASSET_ID,
        subtitle_font_asset_id=DISPLAY_FONT_ASSET_ID,
        body_font_asset_id=FUNCTIONAL_FONT_ASSET_ID,
        artwork_mode="softened_full_background",
        artwork_opacity_range=(0.86, 0.98),
        card_opacity=0.88,
        texture_tokens=("warm_grain", "coffee_blossom"),
        accent_tokens=("amber_rule",),
    ),
    "matcha_refined": VisualTheme(
        theme_id="matcha_refined",
        background_color="#f2f5df",
        card_fill="#fbf8e9",
        card_secondary_fill="#edf3d5",
        primary_text_color="#173f2a",
        secondary_text_color="#2f5b3d",
        accent_color="#6f8f45",
        border_color="#9cb77a",
        title_font_asset_id=DISPLAY_FONT_ASSET_ID,
        subtitle_font_asset_id=DISPLAY_FONT_ASSET_ID,
        body_font_asset_id=FUNCTIONAL_FONT_ASSET_ID,
        artwork_mode="framed_hero_region",
        artwork_opacity_range=(0.9, 1.0),
        card_opacity=0.92,
        texture_tokens=("rice_paper", "tea_leaf"),
        accent_tokens=("sage_rule",),
    ),
    "coffee_roast": VisualTheme(
        theme_id="coffee_roast",
        background_color="#f3ead7",
        card_fill="#f8ecd1",
        card_secondary_fill="#ead5af",
        primary_text_color="#4b2714",
        secondary_text_color="#68401f",
        accent_color="#7a4a1d",
        border_color="#b8894e",
        title_font_asset_id=DISPLAY_FONT_ASSET_ID,
        subtitle_font_asset_id=DISPLAY_FONT_ASSET_ID,
        body_font_asset_id=FUNCTIONAL_FONT_ASSET_ID,
        artwork_mode="softened_full_background",
        artwork_opacity_range=(0.86, 0.98),
        card_opacity=0.86,
        texture_tokens=("kraft_paper", "coffee_leaf"),
        accent_tokens=("roast_rule",),
    ),
    "lotus_premium": VisualTheme(
        theme_id="lotus_premium",
        background_color="#fbf3df",
        card_fill="#fff5da",
        card_secondary_fill="#f2dfb8",
        primary_text_color="#5b3515",
        secondary_text_color="#755128",
        accent_color="#a88b2d",
        border_color="#d6ba62",
        title_font_asset_id=DISPLAY_FONT_ASSET_ID,
        subtitle_font_asset_id=DISPLAY_FONT_ASSET_ID,
        body_font_asset_id=FUNCTIONAL_FONT_ASSET_ID,
        artwork_mode="softened_full_background",
        artwork_opacity_range=(0.88, 0.99),
        card_opacity=0.84,
        texture_tokens=("lotus_paper", "premium_grain"),
        accent_tokens=("lotus_gold_rule",),
    ),
}


def semantic_intent(project: ProjectSpec, plan: DesignPlan, intent: LayoutIntent) -> dict[str, str]:
    product_text = " ".join(
        [project.product.name, project.product.category, project.creative_brief_raw]
    ).lower()
    text = " ".join([product_text, *plan.palette]).lower()
    product_uses_honey = any(token in product_text for token in ["mat ong", "honey"])
    if any(token in product_text for token in ["ca phe", "coffee", "cafe"]):
        palette_mood = "coffee_roast"
        typography_mood = "artisanal_serif"
        card_style = "kraft_coffee"
    elif any(token in product_text for token in ["hat sen", "sen ", "lotus"]):
        palette_mood = "lotus_premium"
        typography_mood = "refined_natural"
        card_style = "lotus_paper"
    elif product_uses_honey:
        palette_mood = "honey_warm"
        typography_mood = "artisanal_serif"
        card_style = "cream_gold"
    elif (
        any(
        token in text for token in ["matcha", "trà xanh", "tra xanh", "tea green", "green"]
        )
        or any(_is_green_hex(color) for color in plan.palette)
    ):
        palette_mood = "matcha_cool"
        typography_mood = "refined_natural"
        card_style = "calm_sage"
    elif any(token in text for token in ["mật ong", "mat ong", "honey"]):
        palette_mood = "honey_warm"
        typography_mood = "artisanal_serif"
        card_style = "cream_gold"
    else:
        raise VisualThemeError("planner palette intent does not map to an approved product theme")
    presence = {"minimal": "soft", "balanced": "balanced", "rich": "rich"}[plan.artwork_density]
    return {
        "typography_mood": typography_mood,
        "palette_mood": palette_mood,
        "artwork_presence": presence,
        "card_style": card_style,
        "planner_artwork_mode": intent.artwork_strategy,
    }


def resolve_visual_theme(
    project: ProjectSpec, plan: DesignPlan, intent: LayoutIntent
) -> tuple[VisualTheme, dict[str, object]]:
    semantic = semantic_intent(project, plan, intent)
    _validate_semantic(semantic)
    theme_id = {
        "honey_warm": "honey_artisanal",
        "matcha_cool": "matcha_refined",
        "coffee_roast": "coffee_roast",
        "lotus_premium": "lotus_premium",
    }[semantic["palette_mood"]]
    theme = THEMES[theme_id]
    if semantic["typography_mood"] == "functional_safe":
        theme = VisualTheme(
            **{
                **theme.__dict__,
                "title_font_asset_id": FUNCTIONAL_FONT_ASSET_ID,
                "subtitle_font_asset_id": FUNCTIONAL_FONT_ASSET_ID,
            }
        )
    diagnostics: dict[str, object] = {
        "planner_intent": dict(semantic),
        "selected_theme": theme.theme_id,
        "resolved_tokens": theme_tokens(theme),
    }
    return theme, diagnostics


def theme_tokens(theme: VisualTheme) -> dict[str, object]:
    return {
        "background_color": theme.background_color,
        "card_fill": theme.card_fill,
        "card_secondary_fill": theme.card_secondary_fill,
        "primary_text_color": theme.primary_text_color,
        "secondary_text_color": theme.secondary_text_color,
        "accent_color": theme.accent_color,
        "border_color": theme.border_color,
        "title_font_asset_id": theme.title_font_asset_id,
        "subtitle_font_asset_id": theme.subtitle_font_asset_id,
        "body_font_asset_id": theme.body_font_asset_id,
        "artwork_mode": theme.artwork_mode,
        "artwork_opacity_range": list(theme.artwork_opacity_range),
        "card_opacity": theme.card_opacity,
        "texture_tokens": list(theme.texture_tokens),
        "accent_tokens": list(theme.accent_tokens),
    }


def artwork_opacity(theme: VisualTheme, mode: str, presence: str, overlaps_text: bool) -> float:
    low, high = theme.artwork_opacity_range
    fraction = {"soft": 0.2, "balanced": 0.55, "rich": 0.85}[presence]
    if mode == "panel_local_decorative_strip":
        fraction = 0.95
    elif mode == "softened_full_background" and overlaps_text:
        fraction = min(fraction, 0.55)
    value = low + (high - low) * fraction
    return round(max(low, min(high, value)), 3)


def visual_theme_qa_results(candidate: LayoutCandidate) -> list[ConstraintResult]:
    theme = candidate.metadata.get("visual_theme", {})
    results = []
    if not isinstance(theme, dict) or not theme.get("theme_id"):
        return [_qa("VIS-00", False, [], "resolved visual theme required")]
    text_colors = [e.metadata.get("text_color") for e in candidate.elements if e.kind == "text"]
    results.append(
        _qa("VIS-01", theme.get("theme_id") in THEMES, [], "approved visual theme selected")
    )
    results.append(
        _qa(
            "VIS-02",
            _contrast(str(theme.get("primary_text_color")), str(theme.get("card_fill"))) >= 4.5,
            ["title_card"],
            "title/card contrast valid",
        )
    )
    results.append(
        _qa(
            "VIS-03",
            all(c and c != "#111111" for c in text_colors),
            [e.element_id for e in candidate.elements if e.kind == "text"],
            "renderer text colors supplied by theme",
        )
    )
    for e in candidate.elements:
        if e.kind == "image" and e.element_id == "artwork_layer":
            low, high = theme.get("artwork_opacity_range", [0, 1])
            opacity = float(e.metadata.get("opacity", -1))
            results.append(
                _qa(
                    "VIS-04",
                    float(low) <= opacity <= float(high),
                    [e.element_id],
                    "artwork opacity inside theme bounds",
                    {"opacity": opacity, "bounds": [low, high]},
                )
            )
    for e in candidate.elements:
        if e.kind == "text":
            role = str(e.metadata.get("role", ""))
            font_id = str(e.metadata.get("font_asset_id", ""))
            if role in DISPLAY_ROLES:
                results.append(
                    _qa(
                        "VIS-05",
                        font_id
                        in {theme.get("title_font_asset_id"), theme.get("subtitle_font_asset_id")},
                        [e.element_id],
                        "display role uses approved theme font",
                    )
                )
            else:
                results.append(
                    _qa(
                        "VIS-06",
                        font_id == FUNCTIONAL_FONT_ASSET_ID,
                        [e.element_id],
                        "functional role stays on safe font",
                    )
                )
    return results


def _validate_semantic(semantic: dict[str, str]) -> None:
    checks = {
        "typography_mood": SUPPORTED_TYPOGRAPHY_MOODS,
        "palette_mood": SUPPORTED_PALETTE_MOODS,
        "artwork_presence": SUPPORTED_ARTWORK_PRESENCE,
        "card_style": SUPPORTED_CARD_STYLES,
    }
    for key, allowed in checks.items():
        if semantic.get(key) not in allowed:
            raise VisualThemeError(f"unsupported planner {key}: {semantic.get(key)}")


def _is_green_hex(value: str) -> bool:
    color = value.strip().lstrip("#")
    if len(color) != 6:
        return False
    try:
        red, green, blue = (int(color[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return False
    return green > red and green >= blue


def _qa(
    rule: str,
    passed: bool,
    elements: list[str],
    message: str,
    details: dict[str, object] | None = None,
) -> ConstraintResult:
    return ConstraintResult(
        rule_id=rule,
        passed=passed,
        severity="critical",
        element_ids=elements,
        message=message,
        details=details or {},
    )


def _contrast(fg: str, bg: str) -> float:
    def lum(hex_color: str) -> float:
        color = hex_color.lstrip("#")
        channels = [int(color[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    a, b = lum(fg), lum(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)
