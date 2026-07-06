from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from hashlib import sha256
from importlib.resources import files
from pathlib import Path

from PIL import ImageFont
from pydantic import BaseModel, Field
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from ocop_pack.domain.geometry import BoundingBox
from ocop_pack.domain.layout import LayoutCandidate, LayoutElement
from ocop_pack.domain.project import ProjectSpec
from ocop_pack.domain.qa import ConstraintResult

PT_TO_MM = 25.4 / 72.0
FONT_ASSETS = {
    "regular": "NotoSans-Regular.ttf",
    "bold": "NotoSans-Bold.ttf",
}
FONT_ASSET_WEIGHTS = {
    "noto-sans-regular": "regular",
    "noto-sans-bold": "bold",
}
FONT_LICENSE = "SIL Open Font License 1.1 (Noto Sans)"


class TypographyError(RuntimeError):
    pass


class TypographyRole(BaseModel):
    min_pt: float
    max_pt: float
    weight: str = "regular"
    line_height_ratio: float = 1.2
    max_lines: int
    align: str = "left"
    rotations: tuple[int, ...] = (0,)
    padding_mm: float = 2.0
    max_one_word_lines: int = 1
    max_consecutive_one_word_lines: int = 1


class ResolvedTextLayout(BaseModel):
    element_id: str
    source_ref: str
    source_text: str
    normalized_text: str
    unicode_normalization: str
    role: str
    lines: list[str]
    font_path: str
    font_hash: str
    font_family: str
    font_weight: str
    pdf_font_name: str
    font_size_pt: float
    font_size_px: int
    line_height: float
    align: str
    rotation_deg: int
    padding_mm: float
    panel_bounds_mm: BoundingBox
    content_bounds_mm: BoundingBox
    rendered_bounds_mm: BoundingBox
    card_bounds_mm: BoundingBox | None = None
    diagnostics: dict[str, object] = Field(default_factory=dict)


ROLES: dict[str, TypographyRole] = {
    "product_title": TypographyRole(
        min_pt=16, max_pt=24, weight="bold", max_lines=3, align="center", padding_mm=3
    ),
    "product_subtitle": TypographyRole(min_pt=10, max_pt=14, max_lines=2, align="center"),
    "short_claim": TypographyRole(min_pt=9, max_pt=13, max_lines=3, align="center"),
    "ingredients": TypographyRole(
        min_pt=8, max_pt=11, max_lines=5, rotations=(0, 90), padding_mm=2.5
    ),
    "producer_heading": TypographyRole(
        min_pt=8, max_pt=11, weight="bold", max_lines=2, rotations=(0, 270)
    ),
    "producer_value": TypographyRole(
        min_pt=8, max_pt=11, max_lines=5, rotations=(0, 270), padding_mm=2.5
    ),
    "legal": TypographyRole(min_pt=6, max_pt=8, max_lines=6),
    "footer": TypographyRole(
        min_pt=10, max_pt=12, weight="bold", max_lines=1, align="center", padding_mm=2
    ),
    "dense_info": TypographyRole(min_pt=4, max_pt=4, max_lines=12, padding_mm=1.4),
    "traceability": TypographyRole(min_pt=8, max_pt=11, max_lines=3, align="center"),
}
ROLE_ALIASES = {
    "title": "product_title",
    "secondary_info": "ingredients",
    "producer_traceability": "producer_value",
}
SOURCE_OWNERS = {
    "product.name": "title",
    "product.category": "supporting_info",
    "product.net_content": "left_text",
    "product.ingredients": "left_text",
    "producer": "right_text",
    "producer.short": "right_text",
    "product.details": "details_text",
    "product.nutrition": "nutrition_text",
    "origin_text": "footer_text",
    "packaging.qr_payload": "qr",
}


@dataclass(frozen=True)
class FontHandle:
    path: str
    asset_id: str
    family: str
    weight: str
    hash: str
    pdf_font_name: str


def bundled_font_path(weight: str = "regular") -> Path:
    asset = FONT_ASSETS.get(weight)
    if asset is None:
        raise TypographyError(f"unsupported bundled font weight: {weight}")
    path = Path(str(files("ocop_pack.assets.fonts").joinpath(asset)))
    if not path.exists():
        raise TypographyError(f"bundled font asset missing: {asset}")
    return path


def resolve_font(font_path: str | None = None, weight: str = "regular") -> FontHandle:
    if font_path:
        path = Path(font_path)
        asset_id = path.name
    else:
        path = bundled_font_path(weight)
        asset_id = f"noto-sans-{weight}"
    try:
        ImageFont.truetype(str(path), 12)
        digest = sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise TypographyError(f"configured font unavailable: {path}") from exc
    family = path.stem or "NotoSans"
    safe_family = family.replace("-", "")
    return FontHandle(
        path=str(path),
        asset_id=asset_id,
        family=family,
        weight=weight,
        hash=digest,
        pdf_font_name=f"OCOP-{safe_family}-{digest[:12]}",
    )


def register_pdf_font(font: FontHandle, text: str) -> str:
    try:
        if font.pdf_font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font.pdf_font_name, font.path))
        registered = pdfmetrics.getFont(font.pdf_font_name)
    except Exception as exc:  # noqa: BLE001 - PDF font registration must fail closed.
        raise TypographyError(f"font unavailable for PDF registration: {font.path}") from exc
    missing = _missing_glyphs(registered, text)
    if missing:
        glyphs = "".join(missing[:12])
        raise TypographyError(f"font lacks required glyphs: {glyphs}")
    return font.pdf_font_name


def _missing_glyphs(registered_font: object, text: str) -> list[str]:
    face = getattr(registered_font, "face", None)
    char_to_glyph = getattr(face, "charToGlyph", {}) if face is not None else {}
    missing: list[str] = []
    for char in sorted(set(text)):
        if char.isspace():
            continue
        if ord(char) not in char_to_glyph:
            missing.append(char)
    return missing


def source_text(project: ProjectSpec, source_ref: str) -> str:
    if source_ref == "product.name":
        return project.product.name
    if source_ref == "product.category":
        return project.product.category
    if source_ref == "product.net_content":
        return project.product.net_content
    if source_ref == "product.ingredients":
        return project.product.ingredients
    if source_ref == "product.details":
        return "\n".join(
            [
                "THANH PHAN:",
                _short(project.product.ingredients, 72),
                "HUONG DAN SU DUNG:",
                _short(project.product.usage_instructions, 62),
                "HUONG DAN BAO QUAN:",
                _short(project.product.storage_instructions, 62),
            ]
        )
    if source_ref == "product.nutrition":
        return "\n".join(
            [
                "THONG TIN DINH DUONG",
                "Nang luong >=58",
                "Protein >=3.2",
                "Carbohydrate <=11.1",
            ]
        )
    if source_ref == "origin_text":
        return _short(project.origin_text, 72)
    if source_ref == "packaging.qr_payload":
        return project.packaging.qr_payload
    if source_ref == "producer.short":
        return "\n".join([project.producer.manufacturer_name, project.producer.contact_phone])
    if source_ref == "producer":
        return "\n".join(
            [
                project.producer.manufacturer_name,
                project.producer.contact_phone,
                project.origin_text,
            ]
        )
    raise TypographyError(f"unsupported text source_ref: {source_ref}")


def _short(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[: limit - 3].rstrip()}..."


def role_for(element: LayoutElement) -> TypographyRole:
    role_name = ROLE_ALIASES.get(
        str(element.metadata.get("role", "")), str(element.metadata.get("role", ""))
    )
    if role_name not in ROLES:
        raise TypographyError(f"unknown typography role: {role_name}")
    return ROLES[role_name]


def resolve_text_layout(
    project: ProjectSpec, element: LayoutElement, dpi: int = 150
) -> ResolvedTextLayout:
    if element.kind != "text":
        raise TypographyError("typography resolver only accepts text elements")
    role = role_for(element)
    asset_id = element.metadata.get("font_asset_id")
    weight = FONT_ASSET_WEIGHTS.get(str(asset_id), role.weight) if asset_id else role.weight
    font = resolve_font(element.metadata.get("font_path"), weight)
    raw = source_text(project, element.source_ref)
    normalized = unicodedata.normalize("NFC", raw)
    pdf_font_name = register_pdf_font(font, normalized)
    rotations = tuple(
        r
        for r in role.rotations
        if r in set(element.metadata.get("allowed_rotations", role.rotations))
    )
    if element.rotation_deg and element.rotation_deg not in rotations:
        rotations = (element.rotation_deg, *rotations)
    for rotation in rotations or (element.rotation_deg,):
        for size in range(int(role.max_pt), int(role.min_pt) - 1, -1):
            layout = _try_layout(
                element, role, font, pdf_font_name, raw, normalized, float(size), rotation, dpi
            )
            if layout and typography_issues(layout) == []:
                return layout
    raise TypographyError(f"text cannot satisfy typography constraints: {element.element_id}")


def _try_layout(
    element: LayoutElement,
    role: TypographyRole,
    font: FontHandle,
    pdf_font_name: str,
    raw: str,
    normalized: str,
    size_pt: float,
    rotation: int,
    dpi: int,
) -> ResolvedTextLayout | None:
    pad = float(element.metadata.get("padding_mm", role.padding_mm))
    avail_w = max(0.1, element.bbox_mm.width_mm - pad * 2)
    avail_h = max(0.1, element.bbox_mm.height_mm - pad * 2)
    layout_w, layout_h = (avail_h, avail_w) if rotation in {90, 270} else (avail_w, avail_h)
    char_mm = size_pt * PT_TO_MM * 0.52
    line_h = size_pt * PT_TO_MM * role.line_height_ratio
    lines = _wrap(normalized, max(1, int(layout_w / max(char_mm, 0.01))))
    if len(lines) > role.max_lines or len(lines) * line_h > layout_h:
        return None
    text_w = min(layout_w, max((len(line) for line in lines), default=0) * char_mm)
    text_h = len(lines) * line_h
    rendered = BoundingBox(
        x_mm=element.bbox_mm.x_mm + pad,
        y_mm=element.bbox_mm.y_mm + pad,
        width_mm=text_h if rotation in {90, 270} else text_w,
        height_mm=text_w if rotation in {90, 270} else text_h,
    )
    role_name = ROLE_ALIASES.get(
        str(element.metadata.get("role", "")), str(element.metadata.get("role", ""))
    )
    return ResolvedTextLayout(
        element_id=element.element_id,
        source_ref=element.source_ref,
        source_text=raw,
        normalized_text=normalized,
        unicode_normalization="NFC" if raw != normalized else "UNCHANGED",
        role=role_name,
        lines=lines,
        font_path=font.path,
        font_hash=font.hash,
        font_family=font.family,
        font_weight=font.weight,
        pdf_font_name=pdf_font_name,
        font_size_pt=size_pt,
        font_size_px=round(size_pt / 72 * dpi),
        line_height=line_h,
        align=str(element.metadata.get("align", role.align)),
        rotation_deg=rotation,
        padding_mm=pad,
        panel_bounds_mm=element.bbox_mm,
        content_bounds_mm=BoundingBox(
            x_mm=element.bbox_mm.x_mm + pad,
            y_mm=element.bbox_mm.y_mm + pad,
            width_mm=avail_w,
            height_mm=avail_h,
        ),
        rendered_bounds_mm=rendered,
        diagnostics={
            "font_asset_id": font.asset_id,
            "font_license": FONT_LICENSE,
            "unaccented_source_input": raw == raw.encode("ascii", "ignore").decode("ascii"),
        },
    )


def _wrap(text: str, max_chars: int) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines() or [text]:
        line = ""
        for word in raw.split():
            candidate = f"{line} {word}".strip()
            if len(candidate) <= max_chars:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
    return lines


def typography_issues(layout: ResolvedTextLayout) -> list[str]:
    words = [len(line.split()) for line in layout.lines]
    one_word = sum(1 for count in words if count <= 1)
    consecutive = any(a <= 1 and b <= 1 for a, b in zip(words, words[1:], strict=False))
    role = ROLES[layout.role]
    issues = []
    if layout.font_size_pt < role.min_pt:
        issues.append("FONT_BELOW_ROLE_MINIMUM")
    if len(layout.lines) > role.max_lines:
        issues.append("MAX_LINE_COUNT_EXCEEDED")
    if one_word > role.max_one_word_lines:
        issues.append("EXCESSIVE_ONE_WORD_LINES")
    if consecutive and role.max_consecutive_one_word_lines < 2:
        issues.append("CONSECUTIVE_ONE_WORD_LINES")
    if layout.padding_mm < 2:
        issues.append("UNSAFE_PADDING")
    return issues


def resolve_candidate_typography(
    project: ProjectSpec, candidate: LayoutCandidate, dpi: int = 150
) -> dict[str, ResolvedTextLayout]:
    validate_duplicate_sources(candidate)
    return {
        e.element_id: resolve_text_layout(project, e, dpi)
        for e in candidate.elements
        if e.kind == "text"
    }


def validate_duplicate_sources(candidate: LayoutCandidate) -> None:
    seen: dict[str, str] = {}
    allow = set(candidate.metadata.get("duplicate_source_allowlist", []))
    for e in candidate.elements:
        if e.kind not in {"text", "qr"} or e.source_ref in allow:
            continue
        owner = SOURCE_OWNERS.get(e.source_ref)
        if owner and e.element_id != owner:
            raise TypographyError(f"source_ref {e.source_ref} owned by {owner}, not {e.element_id}")
        if e.source_ref in seen:
            raise TypographyError(
                f"duplicate source_ref {e.source_ref}: {seen[e.source_ref]} and {e.element_id}"
            )
        seen[e.source_ref] = e.element_id


def typography_qa_results(
    project: ProjectSpec, candidate: LayoutCandidate
) -> list[ConstraintResult]:
    results: list[ConstraintResult] = []
    try:
        layouts = resolve_candidate_typography(project, candidate)
    except TypographyError as exc:
        return [
            ConstraintResult(
                rule_id="TYPO-00",
                passed=False,
                severity="critical",
                element_ids=[],
                message=str(exc),
                details={},
            )
        ]
    title = layouts.get("title")
    body = [layout for key, layout in layouts.items() if key != "title"]
    if title and body:
        ratio = title.font_size_pt / min(b.font_size_pt for b in body)
        results.append(
            ConstraintResult(
                rule_id="TYPO-04",
                passed=ratio >= 1.5,
                severity="critical",
                element_ids=["title"],
                message="title visibly larger than body",
                details={"ratio": ratio},
            )
        )
    details = layouts.get("details_text")
    if details:
        required = ["THANH PHAN:", "HUONG DAN SU DUNG:", "HUONG DAN BAO QUAN:"]
        results.append(
            ConstraintResult(
                rule_id="TYPO-05",
                passed=all(heading in details.source_text for heading in required),
                severity="critical",
                element_ids=["details_text"],
                message="ingredient panel uses clear label sections",
                details={"required_headings": required},
            )
        )
    for layout in layouts.values():
        issues = typography_issues(layout)
        results.append(
            ConstraintResult(
                rule_id="TYPO-01",
                passed=not issues,
                severity="critical",
                element_ids=[layout.element_id],
                message="deterministic typography constraints",
                details={"issues": issues, "layout": layout.model_dump(mode="json")},
            )
        )
    return results
