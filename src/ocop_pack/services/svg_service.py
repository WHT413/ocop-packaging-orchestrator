from __future__ import annotations

import base64
from pathlib import Path
from xml.sax.saxutils import escape

from ocop_pack.domain.dieline import DielineSpec
from ocop_pack.domain.layout import LayoutManifest
from ocop_pack.domain.project import ProjectSpec
from ocop_pack.engine.qr import render_qr_square
from ocop_pack.engine.typography import resolve_text_layout


def render_svg_manifest(
    manifest: LayoutManifest, project: ProjectSpec, dieline: DielineSpec, out: Path
) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{dieline.width_mm}mm" '
            f'height="{dieline.height_mm}mm" viewBox="0 0 {dieline.width_mm} {dieline.height_mm}">'
        ),
    ]
    for element in sorted(manifest.candidate.elements, key=lambda item: item.z_index):
        box = element.bbox_mm
        if element.kind == "shape":
            parts.append(
                f'<rect x="{box.x_mm}" y="{box.y_mm}" width="{box.width_mm}" '
                f'height="{box.height_mm}" rx="{element.metadata.get("corner_radius_mm", 0)}" '
                f'fill="{escape(str(element.metadata.get("fill", "#ffffff")))}" '
                f'opacity="{float(element.metadata.get("opacity", 1.0))}" />'
            )
        elif element.kind == "text":
            layout = resolve_text_layout(project, element)
            y = box.y_mm + layout.padding_mm + layout.font_size_pt * 25.4 / 72
            anchor = "middle" if layout.align == "center" else "start"
            x = (
                box.x_mm + box.width_mm / 2
                if layout.align == "center"
                else box.x_mm + layout.padding_mm
            )
            for line in layout.lines:
                parts.append(
                    f'<text x="{x}" y="{y}" font-family="Noto Sans" '
                    f'font-size="{layout.font_size_pt * 25.4 / 72}mm" '
                    f'font-weight="{layout.font_weight}" text-anchor="{anchor}" '
                    f'fill="{escape(str(element.metadata.get("text_color", "#111111")))}">'
                    f"{escape(line)}</text>"
                )
                y += layout.line_height
        elif element.kind == "qr":
            qr_tmp = out.with_suffix(".qr.tmp.png")
            render_qr_square(project.packaging.qr_payload, (512, 512))[0].save(qr_tmp)
            parts.append(_image_tag(qr_tmp, box.x_mm, box.y_mm, box.width_mm, box.height_mm))
            qr_tmp.unlink(missing_ok=True)
        elif element.kind == "image":
            path = Path(str(manifest.artwork_refs[element.source_ref.split(":", 1)[1]]))
            parts.append(
                _image_tag(
                    path,
                    box.x_mm,
                    box.y_mm,
                    box.width_mm,
                    box.height_mm,
                    float(element.metadata.get("opacity", 1.0)),
                )
            )
        elif element.kind == "group" and element.source_ref == "branding.ocop.logo_path":
            parts.append(
                _image_tag(
                    project.branding.ocop.logo_path,
                    box.x_mm,
                    box.y_mm,
                    box.width_mm,
                    box.height_mm,
                )
            )
        elif element.kind == "vector":
            continue
        else:
            raise ValueError(f"unsupported SVG element kind: {element.kind}")
    parts.append("</svg>")
    out.write_text("\n".join(parts), encoding="utf-8")
    return out


def _image_tag(
    path: Path, x: float, y: float, width: float, height: float, opacity: float = 1.0
) -> str:
    suffix = path.suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return (
        f'<image x="{x}" y="{y}" width="{width}" height="{height}" '
        f'opacity="{opacity}" preserveAspectRatio="xMidYMid meet" '
        f'href="data:{mime};base64,{encoded}" />'
    )
