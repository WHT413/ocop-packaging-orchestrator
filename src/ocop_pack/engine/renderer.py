from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdf_canvas

from ocop_pack.domain.dieline import DielineSpec
from ocop_pack.domain.project import ProjectSpec
from ocop_pack.engine.qr import generate_qr
from ocop_pack.engine.scene import Scene


def mm_to_px(value_mm: float, dpi: int) -> int:
    return round(value_mm / 25.4 * dpi)


def render_png(scene: Scene, project: ProjectSpec, out: Path, dpi: int = 150) -> Path:
    img = Image.new("RGB", (mm_to_px(scene.width_mm, dpi), mm_to_px(scene.height_mm, dpi)), "white")
    draw = ImageDraw.Draw(img)
    font = _font(24)
    for e in sorted(scene.elements, key=lambda x: x.z_index):
        box = [
            mm_to_px(e.bbox_mm.x_mm, dpi),
            mm_to_px(e.bbox_mm.y_mm, dpi),
            mm_to_px(e.bbox_mm.right, dpi),
            mm_to_px(e.bbox_mm.bottom, dpi),
        ]
        if e.kind == "shape":
            draw.rectangle(box, fill=str(e.metadata.get("fill", "#ffffff")))
        elif e.kind == "text":
            draw.multiline_text(
                (box[0], box[1]), _text(project, e.source_ref), fill="#111111", font=font, spacing=4
            )
        elif e.kind == "qr":
            qr = generate_qr(project.packaging.qr_payload)
            img.paste(qr.resize((box[2] - box[0], box[3] - box[1])), (box[0], box[1]))
        elif e.kind == "group":
            draw.rounded_rectangle(box, radius=6, fill="#ffffff", outline="#cc8a00", width=2)
            draw.text(
                (box[0] + 4, box[1] + 4),
                f"OCOP {'*' * int(e.metadata.get('star_count', 0))}",
                fill="#b15b00",
                font=font,
            )
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, dpi=(dpi, dpi))
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
            c.rect(x, y, w, h, fill=1, stroke=0)
        elif e.kind == "text":
            c.setFillColor("#111111")
            c.drawString(x, y + h - 10, _text(project, e.source_ref)[:120])
        elif e.kind == "group":
            c.setFillColor("#ffffff")
            c.rect(x, y, w, h, fill=1, stroke=1)
            c.setFillColor("#b15b00")
            c.drawString(
                x + 3 * mm, y + h / 2, f"OCOP {'*' * int(e.metadata.get('star_count', 0))}"
            )
        elif e.kind == "qr":
            tmp = out.with_suffix(".qr.png")
            generate_qr(project.packaging.qr_payload).save(tmp)
            c.drawImage(str(tmp), x, y, w, h)
            tmp.unlink(missing_ok=True)
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
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _text(project: ProjectSpec, source: str) -> str:
    if source == "product.name":
        return project.product.name
    if source == "product.ingredients":
        return project.product.ingredients
    return "\n".join(
        [project.producer.manufacturer_name, project.producer.contact_phone, project.origin_text]
    )
