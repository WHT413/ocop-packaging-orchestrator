from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdf_canvas

from ocop_pack.domain.dieline import DielineSpec
from ocop_pack.domain.layout import LayoutElement
from ocop_pack.domain.project import ProjectSpec
from ocop_pack.engine.qr import qr_render_metadata, render_qr_square, square_inside_bbox
from ocop_pack.engine.scene import Scene, SceneElement
from ocop_pack.engine.typography import (
    TypographyError,
    register_pdf_font,
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
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            _draw_shape(layer, e, box, fill, radius, dpi)
            img.alpha_composite(layer)
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
            layer = _load_ocop_layer(project, e, (box[2] - box[0], box[3] - box[1]))
            img.alpha_composite(layer, (box[0], box[1]))
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
            tmp = out.with_suffix(".ocop.png")
            _load_ocop_layer(project, e, (1024, 512)).save(tmp)
            c.drawImage(
                str(tmp),
                x,
                y,
                w,
                h,
                preserveAspectRatio=True,
                mask="auto",
            )
            tmp.unlink(missing_ok=True)
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


def _resolve_ocop_path(project: ProjectSpec, source_ref: str) -> Path:
    if source_ref != "branding.ocop.logo_path":
        raise RenderAssetError(f"unsupported group source: {source_ref}")
    path = project.branding.ocop.logo_path
    if not path.exists():
        raise RenderAssetError(f"OCOP logo file not found: {path}")
    return path


def _resolve_ocop_variant_path(project: ProjectSpec, e: SceneElement) -> Path:
    base = _resolve_ocop_path(project, e.source_ref)
    star_count = int(e.metadata.get("star_count", project.branding.ocop.star_count))
    variant = base.with_name(f"ocop_{star_count}_star{base.suffix}")
    return variant if variant.exists() else base


def _rgba(color: str, opacity: float) -> tuple[int, int, int, int]:
    color = color.lstrip("#")
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    return r, g, b, max(0, min(255, round(opacity * 255)))


def _draw_shape(
    layer: Image.Image,
    e: SceneElement,
    box: list[int],
    fill: tuple[int, int, int, int],
    radius: int,
    dpi: int,
) -> None:
    draw = ImageDraw.Draw(layer)
    style = str(e.metadata.get("frame_style", "paper_label"))
    border_width = int(mm_to_px(float(e.metadata.get("border_width_mm", 0)), dpi))
    border_color = str(e.metadata.get("border_color", "#000000"))
    outline = _rgba(border_color, 1.0) if border_width > 0 else None
    if style == "torn_paper":
        draw.polygon(_rough_box_points(e.element_id, box), fill=fill)
        return
    if style == "leaf_badge":
        _draw_badge_shape(draw, e, box, fill)
        return
    if style == "brush_stroke":
        draw.polygon(_rough_box_points(e.element_id, box, steps=5), fill=fill)
        return
    if radius > 0:
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=border_width)
    else:
        draw.rectangle(box, fill=fill, outline=outline, width=border_width)
    if style == "woven_label":
        line = (max(0, fill[0] - 35), max(0, fill[1] - 35), max(0, fill[2] - 35), fill[3] // 5)
        step = max(6, (box[2] - box[0]) // 9)
        for x in range(box[0], box[2], step):
            draw.line((x, box[1], x, box[3]), fill=line, width=1)
        for y in range(box[1], box[3], step):
            draw.line((box[0], y, box[2], y), fill=line, width=1)


def _rough_box_points(element_id: str, box: list[int], steps: int = 8) -> list[tuple[int, int]]:
    digest = sha256(element_id.encode("utf-8")).digest()
    jitter = max(1, min(box[2] - box[0], box[3] - box[1]) // 16)
    points: list[tuple[int, int]] = []
    edges = [
        ((box[0], box[1]), (box[2], box[1])),
        ((box[2], box[1]), (box[2], box[3])),
        ((box[2], box[3]), (box[0], box[3])),
        ((box[0], box[3]), (box[0], box[1])),
    ]
    idx = 0
    for start, end in edges:
        for step in range(steps):
            t = step / steps
            x = round(start[0] + (end[0] - start[0]) * t)
            y = round(start[1] + (end[1] - start[1]) * t)
            offset = digest[idx % len(digest)] % (jitter * 2 + 1) - jitter
            if start[1] == end[1]:
                y += offset
            else:
                x += offset
            points.append((x, y))
            idx += 1
    return points


def _draw_badge_shape(
    draw: ImageDraw.ImageDraw,
    e: SceneElement,
    box: list[int],
    fill: tuple[int, int, int, int],
) -> None:
    motif = str(e.metadata.get("badge_motif", "leaf"))
    w, h = box[2] - box[0], box[3] - box[1]
    if motif == "coffee_bean":
        draw.ellipse(box, fill=fill)
        line = (max(0, fill[0] - 50), max(0, fill[1] - 50), max(0, fill[2] - 50), fill[3] // 3)
        arc_box = (
            box[0] + w * 0.34,
            box[1] + h * 0.12,
            box[2] - w * 0.22,
            box[3] - h * 0.12,
        )
        draw.arc(arc_box, 80, 280, fill=line, width=max(1, w // 28))
        return
    if motif == "honey_drop":
        draw.polygon(
            [
                (box[0] + w * 0.5, box[1]),
                (box[2], box[1] + h * 0.55),
                (box[0] + w * 0.5, box[3]),
                (box[0], box[1] + h * 0.55),
            ],
            fill=fill,
        )
        return
    if motif == "banana_slice":
        draw.pieslice(box, 205, 515, fill=fill)
        return
    if motif in {"lotus_seed", "berry"}:
        draw.rounded_rectangle(box, radius=max(2, min(w, h) // 2), fill=fill)
        return
    draw.ellipse(box, fill=fill)
    draw.polygon(
        [
            (box[0] + w * 0.08, box[1] + h * 0.55),
            (box[0] - w * 0.12, box[1] + h * 0.40),
            (box[0] + w * 0.08, box[1] + h * 0.30),
        ],
        fill=fill,
    )
    draw.polygon(
        [
            (box[2] - w * 0.08, box[1] + h * 0.45),
            (box[2] + w * 0.12, box[1] + h * 0.60),
            (box[2] - w * 0.08, box[1] + h * 0.70),
        ],
        fill=fill,
    )


def _draw_text(
    img: Image.Image, project: ProjectSpec, e: SceneElement, box: list[int], dpi: int
) -> None:
    try:
        layout = resolve_text_layout(project, LayoutElement.model_validate(e.model_dump()), dpi)
    except TypographyError as exc:
        raise RenderAssetError(str(exc)) from exc
    font = ImageFont.truetype(layout.font_path, layout.font_size_px)
    heading_scale = _heading_scale(layout.role)
    header_font = ImageFont.truetype(
        resolve_font(weight="bold").path, round(layout.font_size_px * heading_scale)
    )
    layer = Image.new("RGBA", (max(1, box[2] - box[0]), max(1, box[3] - box[1])), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    padding = mm_to_px(layout.padding_mm, dpi)
    y = padding
    for line in layout.lines:
        line_font = header_font if _is_section_heading(line) else font
        line_w = draw.textlength(line, font=line_font)
        x = padding if layout.align != "center" else (layer.width - line_w) / 2
        color = str(e.metadata.get("text_color", ""))
        if not color.startswith("#"):
            raise RenderAssetError(f"missing theme text color: {e.element_id}")
        draw.text((x, y), line, fill=color, font=line_font)
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
    header_font = resolve_font(weight="bold")
    header_pdf_font = register_pdf_font(header_font, layout.normalized_text)
    pad = layout.padding_mm * mm
    if layout.rotation_deg:
        c.translate(x + w / 2, y + h / 2)
        c.rotate(layout.rotation_deg)
        tx, ty = -h / 2 + pad, w / 2 - pad - layout.font_size_pt
    else:
        tx, ty = x + pad, y + h - pad - layout.font_size_pt
    for offset, line in enumerate(layout.lines):
        if _is_section_heading(line):
            c.setFont(header_pdf_font, layout.font_size_pt * _heading_scale(layout.role))
        else:
            c.setFont(layout.pdf_font_name, layout.font_size_pt)
        c.drawString(tx, ty - offset * layout.line_height * mm, line)
    c.restoreState()


def _heading_scale(role: str) -> float:
    return 1.0 if role == "dense_info" else 1.18


def _is_section_heading(line: str) -> bool:
    stripped = line.strip()
    return stripped.endswith(":") or stripped in {"THONG TIN DINH DUONG"}


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


def _load_ocop_layer(project: ProjectSpec, e: SceneElement, size: tuple[int, int]) -> Image.Image:
    if size[0] <= 0 or size[1] <= 0:
        raise RenderAssetError("OCOP logo has invalid target size")
    try:
        with Image.open(_resolve_ocop_variant_path(project, e)) as source:
            image = source.convert("RGBA")
    except Exception as exc:  # noqa: BLE001 - fail closed with domain error.
        raise RenderAssetError("invalid OCOP logo image") from exc
    contained = ImageOps.contain(image, size, Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    layer.alpha_composite(
        contained,
        ((size[0] - contained.width) // 2, (size[1] - contained.height) // 2),
    )
    return layer
