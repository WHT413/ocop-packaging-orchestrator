from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from ocop_pack.domain.layout import LayoutCandidate
from ocop_pack.orchestration.idempotency import stable_hash

CONTACT_SHEET_RENDERER_VERSION = "contact-sheet.v1"


class ContactSheetManifest(BaseModel):
    contact_sheet_hash: str
    candidate_ids: list[str]
    candidate_hashes: dict[str, str]
    candidate_order: list[str]
    thumbnail_dimensions: tuple[int, int]
    renderer_version: str = CONTACT_SHEET_RENDERER_VERSION
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


def select_top_k(
    candidates: list[LayoutCandidate], top_k: int = 6, hard_max: int = 8
) -> list[LayoutCandidate]:
    limit = max(0, min(top_k, hard_max))
    ranked = sorted(
        candidates,
        key=lambda c: (-(float(c.metadata.get("score", 0.0))), c.candidate_id),
    )
    selected: list[LayoutCandidate] = []
    for family in sorted({str(c.metadata.get("template_family", "")) for c in ranked}):
        match = next(
            (c for c in ranked if str(c.metadata.get("template_family", "")) == family), None
        )
        if match and len(selected) < limit:
            selected.append(match)
    for candidate in ranked:
        if len(selected) >= limit:
            break
        if candidate not in selected:
            selected.append(candidate)
    return selected


def render_contact_sheet(
    previews: dict[str, Path],
    candidates: list[LayoutCandidate],
    output_png: Path,
    manifest_json: Path,
    columns: int = 3,
    thumbnail_size: tuple[int, int] = (360, 240),
) -> ContactSheetManifest:
    ordered = sorted(candidates, key=lambda c: c.candidate_id)
    rows = max(1, (len(ordered) + columns - 1) // columns)
    label_h = 34
    padding = 16
    sheet = Image.new(
        "RGB",
        (
            columns * (thumbnail_size[0] + padding) + padding,
            rows * (thumbnail_size[1] + label_h + padding) + padding,
        ),
        "#f2f2ef",
    )
    draw = ImageDraw.Draw(sheet)
    font = _font(18)
    for index, candidate in enumerate(ordered):
        col = index % columns
        row = index // columns
        x = padding + col * (thumbnail_size[0] + padding)
        y = padding + row * (thumbnail_size[1] + label_h + padding)
        thumb = _fit_thumbnail(Image.open(previews[candidate.candidate_id]), thumbnail_size)
        sheet.paste(thumb, (x, y))
        draw.rectangle((x, y, x + thumbnail_size[0], y + thumbnail_size[1]), outline="#333333")
        draw.text(
            (x + 8, y + thumbnail_size[1] + 6),
            candidate.candidate_id,
            fill="#111111",
            font=font,
        )
    output_png.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_png, format="PNG")
    digest = _file_hash(output_png)
    manifest = ContactSheetManifest(
        contact_sheet_hash=digest,
        candidate_ids=[c.candidate_id for c in ordered],
        candidate_hashes={c.candidate_id: stable_hash(c.model_dump(mode="json")) for c in ordered},
        candidate_order=[c.candidate_id for c in ordered],
        thumbnail_dimensions=thumbnail_size,
    )
    manifest_json.parent.mkdir(parents=True, exist_ok=True)
    manifest_json.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest


def _fit_thumbnail(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGB", size, "white")
    copy = image.convert("RGB")
    copy.thumbnail(size, Image.Resampling.LANCZOS)
    x = (size[0] - copy.width) // 2
    y = (size[1] - copy.height) // 2
    canvas.paste(copy, (x, y))
    return canvas


def _file_hash(path: Path) -> str:
    h = sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()
