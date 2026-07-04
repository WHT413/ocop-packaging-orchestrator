from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdf_canvas

from ocop_pack.domain.dieline import DielineSpec
from ocop_pack.domain.layout import LayoutElement
from ocop_pack.domain.project import ProjectSpec
from ocop_pack.engine.qr import qr_render_metadata, render_qr_square, square_inside_bbox
from ocop_pack.engine.scene import Scene, SceneElement
from ocop_pack.engine.typography import (
    TypographyError,
    resolve_font,
    resolve_text_layout,
)


class RenderAssetError(RuntimeError):
    pass


MIN_QR_RENDER_PX = 96


def mm_to_px(value_mm: float, dpi: int) -> int:
    return round(value_mm / 25.4 * dpi)


def render_png(scene: Scene, project: ProjectSpec, out: Path, dpi: int = 150) -> Path:
    img = Image.new(
        "RGBA", (mm_to_px(scene.width_mm, dpi), mm_to_px(scene.height_mm, dpi)), "white"
    )
    for e in sorted(scene.elements, key=lambda x: x.z_index):
        draw = ImageDraw.Draw(img)
        box = [
            mm_to_px(e.bbox_mm.x_mm, dpi),
            mm_to_px(e.bbox_mm.y_mm, dpi),
            mm_to_px(e.bbox_mm.right, dpi),
            mm_to_px(e.bbox_mm.bottom, dpi),
        ]
        if e.kind == "shape":
            fill = _rgba(
                str(e.metadata.get("fill", "#ffffff")), float(e.metadata.get("opacity", 1.0))
            )
            radius = mm_to_px(float(e.metadata.get("corner_radius_mm", 0)), dpi)
            if radius > 0:
                draw.rounded_rectangle(box, radius=radius, fill=fill)
            else:
                draw.rectangle(box, fill=fill)
        elif e.kind == "text":
            _draw_text(img, project, e, box, dpi)
        elif e.kind == "qr":
            target_size = (box[2] - box[0], box[3] - box[1])
            if min(target_size) < MIN_QR_RENDER_PX:
                layer, _ = render_qr_square(
                    project.packaging.qr_payload, (MIN_QR_RENDER_PX, MIN_QR_RENDER_PX)
                )
                layer = layer.resize(target_size, Image.Resampling.NEAREST)
            else:
                layer, _ = render_qr_square(project.packaging.qr_payload, target_size)
            img.alpha_composite(layer.convert("RGBA"), (box[0], box[1]))
        elif e.kind == "image":
            layer = _load_image_layer(scene, e, (box[2] - box[0], box[3] - box[1]))
            img.alpha_composite(layer, (box[0], box[1]))
        elif e.kind == "group":
            font = _font(24)
            theme = (
                scene.metadata.get("visual_theme", {}) if isinstance(scene.metadata, dict) else {}
            )
            outline = (
                str(theme.get("border_color", e.metadata.get("border_color", "#cc8a00")))
                if isinstance(theme, dict)
                else "#cc8a00"
            )
            accent = (
                str(theme.get("accent_color", e.metadata.get("accent_color", "#b15b00")))
                if isinstance(theme, dict)
                else "#b15b00"
            )
            draw.rounded_rectangle(box, radius=6, fill="#ffffff", outline=outline, width=2)
            draw.text(
                (box[0] + 4, box[1] + 4),
                f"OCOP {'*' * int(e.metadata.get('star_count', 0))}",
                fill=accent,
                font=font,
            )
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, dpi=(dpi, dpi))
    return out


def render_pdf(scene: Scene, project: ProjectSpec, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    c = pdf_canvas.Canvas(str(out), pagesize=(scene.width_mm * mm, scene.height_mm * mm))
    c.setAuthor("ocop-pack deterministic core")
    c.setTitle(f"{scene.run_id}:{scene.project_id}")
    for e in sorted(scene.elements, key=lambda x: x.z_index):
        x, y, w, h = (
            e.bbox_mm.x_mm * mm,
            (scene.height_mm - e.bbox_mm.bottom) * mm,
            e.bbox_mm.width_mm * mm,
            e.bbox_mm.height_mm * mm,
        )
        if e.kind == "shape":
            c.setFillColor(str(e.metadata.get("fill", "#ffffff")))
            c.setFillAlpha(float(e.metadata.get("opacity", 1.0)))
            c.rect(x, y, w, h, fill=1, stroke=0)
            c.setFillAlpha(1)
        elif e.kind == "text":
            _draw_pdf_text(c, project, e, x, y, w, h)
        elif e.kind == "group":
            theme = (
                scene.metadata.get("visual_theme", {}) if isinstance(scene.metadata, dict) else {}
            )
            accent = (
                str(theme.get("accent_color", e.metadata.get("accent_color", "#b15b00")))
                if isinstance(theme, dict)
                else "#b15b00"
            )
            c.setFillColor("#ffffff")
            c.rect(x, y, w, h, fill=1, stroke=1)
            c.setFillColor(accent)
            c.drawString(
                x + 3 * mm, y + h / 2, f"OCOP {'*' * int(e.metadata.get('star_count', 0))}"
            )
        elif e.kind == "qr":
            tmp = out.with_suffix(".qr.png")
            square = square_inside_bbox(e.bbox_mm)
            qr_render_metadata(project.packaging.qr_payload, e.bbox_mm)
            render_qr_square(project.packaging.qr_payload, (512, 512))[0].save(tmp)
            c.setFillColor("#ffffff")
            c.rect(x, y, w, h, fill=1, stroke=0)
            qx = square.x_mm * mm
            qy = (scene.height_mm - square.bottom) * mm
            qw = square.width_mm * mm
            c.drawImage(str(tmp), qx, qy, qw, qw)
            tmp.unlink(missing_ok=True)
        elif e.kind == "image":
            path = _resolve_image_path(scene, e.source_ref)
            c.saveState()
            c.setFillAlpha(float(e.metadata.get("opacity", 1.0)))
            c.drawImage(
                str(path),
                x,
                y,
                w,
                h,
                preserveAspectRatio=e.metadata.get("fit") == "contain",
                mask="auto",
            )
            c.restoreState()
        else:
            raise RenderAssetError(f"unsupported scene element kind: {e.kind}")
    c.showPage()
    c.save()
    return out


def render_dieline_overlay(dieline: DielineSpec, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    c = pdf_canvas.Canvas(str(out), pagesize=(dieline.width_mm * mm, dieline.height_mm * mm))
    c.setStrokeColor("#ff0000")
    for x in dieline.vertical_folds_x_mm:
        c.line(x * mm, 0, x * mm, dieline.height_mm * mm)
    for y in dieline.horizontal_folds_y_mm:
        c.line(0, y * mm, dieline.width_mm * mm, y * mm)
    c.showPage()
    c.save()
    return out


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.truetype(resolve_font().path, size)


def _text(project: ProjectSpec, source: str) -> str:
    if source == "product.name":
        return project.product.name
    if source == "product.ingredients":
        return project.product.ingredients
    return "\n".join(
        [project.producer.manufacturer_name, project.producer.contact_phone, project.origin_text]
    )


def _resolve_image_path(scene: Scene, source_ref: str) -> Path:
    if not source_ref.startswith("artwork:"):
        raise RenderAssetError(f"unsupported image source: {source_ref}")
    artwork_id = source_ref.split(":", 1)[1]
    refs = scene.metadata.get("artwork_refs", {})
    if not isinstance(refs, dict) or artwork_id not in refs:
        raise RenderAssetError(f"missing artwork ref: {artwork_id}")
    path = Path(str(refs[artwork_id]))
    if not path.exists():
        raise RenderAssetError(f"artwork file not found: {path}")
    return path


def _rgba(color: str, opacity: float) -> tuple[int, int, int, int]:
    color = color.lstrip("#")
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    return r, g, b, max(0, min(255, round(opacity * 255)))


def _draw_text(
    img: Image.Image, project: ProjectSpec, e: SceneElement, box: list[int], dpi: int
) -> None:
    try:
        layout = resolve_text_layout(project, LayoutElement.model_validate(e.model_dump()), dpi)
    except TypographyError as exc:
        raise RenderAssetError(str(exc)) from exc
    font = ImageFont.truetype(layout.font_path, layout.font_size_px)
    layer = Image.new("RGBA", (max(1, box[2] - box[0]), max(1, box[3] - box[1])), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    padding = mm_to_px(layout.padding_mm, dpi)
    y = padding
    for line in layout.lines:
        line_w = draw.textlength(line, font=font)
        x = padding if layout.align != "center" else (layer.width - line_w) / 2
        color = str(e.metadata.get("text_color", ""))
        if not color.startswith("#"):
            raise RenderAssetError(f"missing theme text color: {e.element_id}")
        draw.text((x, y), line, fill=color, font=font)
        y += mm_to_px(layout.line_height, dpi)
    if layout.rotation_deg:
        layer = layer.rotate(layout.rotation_deg, expand=True)
        layer.thumbnail((box[2] - box[0], box[3] - box[1]), Image.Resampling.LANCZOS)
    img.alpha_composite(
        layer,
        (
            box[0] + (box[2] - box[0] - layer.width) // 2,
            box[1] + (box[3] - box[1] - layer.height) // 2,
        ),
    )


def _draw_pdf_text(
    c: pdf_canvas.Canvas,
    project: ProjectSpec,
    e: SceneElement,
    x: float,
    y: float,
    w: float,
    h: float,
) -> None:
    try:
        layout = resolve_text_layout(project, LayoutElement.model_validate(e.model_dump()))
    except TypographyError as exc:
        raise RenderAssetError(str(exc)) from exc
    c.saveState()
    color = str(e.metadata.get("text_color", ""))
    if not color.startswith("#"):
        raise RenderAssetError(f"missing theme text color: {e.element_id}")
    c.setFillColor(color)
    c.setFont(layout.pdf_font_name, layout.font_size_pt)
    pad = layout.padding_mm * mm
    if layout.rotation_deg:
        c.translate(x + w / 2, y + h / 2)
        c.rotate(layout.rotation_deg)
        tx, ty = -h / 2 + pad, w / 2 - pad - layout.font_size_pt
    else:
        tx, ty = x + pad, y + h - pad - layout.font_size_pt
    for offset, line in enumerate(layout.lines):
        c.drawString(tx, ty - offset * layout.line_height * mm, line)
    c.restoreState()


def _wrap_text(text: str, max_chars: int) -> list[str]:
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


def _load_image_layer(scene: Scene, e: SceneElement, size: tuple[int, int]) -> Image.Image:
    if size[0] <= 0 or size[1] <= 0:
        raise RenderAssetError("image layer has invalid target size")
    path = _resolve_image_path(scene, e.source_ref)
    try:
        with Image.open(path) as source:
            image = source.convert("RGBA")
    except Exception as exc:  # noqa: BLE001 - fail closed with domain error.
        raise RenderAssetError(f"invalid artwork image: {path}") from exc
    if image.width <= 0 or image.height <= 0:
        raise RenderAssetError(f"invalid artwork dimensions: {path}")
    fit = str(e.metadata.get("fit", "cover"))
    if fit not in {"cover", "contain"}:
        raise RenderAssetError(f"unsupported image fit: {fit}")
    if fit == "cover":
        image_ratio = image.width / image.height
        target_ratio = size[0] / size[1]
        if image_ratio > target_ratio:
            new_width = round(image.height * target_ratio)
            left = (image.width - new_width) // 2
            image = image.crop((left, 0, left + new_width, image.height))
        else:
            new_height = round(image.width / target_ratio)
            top = (image.height - new_height) // 2
            image = image.crop((0, top, image.width, top + new_height))
        layer = image.resize(size, Image.Resampling.LANCZOS)
    else:
        image.thumbnail(size, Image.Resampling.LANCZOS)
        layer = Image.new("RGBA", size, (0, 0, 0, 0))
        layer.alpha_composite(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
    opacity = float(e.metadata.get("opacity", 1.0))
    if opacity < 1:
        alpha = layer.getchannel("A").point(lambda v: round(v * opacity))
        layer.putalpha(alpha)
    return layer
