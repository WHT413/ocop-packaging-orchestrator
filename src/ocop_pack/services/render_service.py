from __future__ import annotations

from pathlib import Path

from ocop_pack.domain.dieline import DielineSpec
from ocop_pack.domain.layout import LayoutManifest
from ocop_pack.domain.project import ProjectSpec
from ocop_pack.engine.renderer import render_dieline_overlay, render_pdf, render_png
from ocop_pack.engine.scene import scene_from_manifest


def render_manifest(
    manifest: LayoutManifest, project: ProjectSpec, dieline: DielineSpec, out_dir: Path
) -> tuple[Path, Path, Path]:
    scene = scene_from_manifest(manifest, dieline.width_mm, dieline.height_mm)
    png = render_png(scene, project, out_dir / "final" / "final_preview.png")
    pdf = render_pdf(scene, project, out_dir / "final" / "final_design.pdf")
    overlay = render_dieline_overlay(dieline, out_dir / "geometry" / "dieline_overlay.pdf")
    return png, pdf, overlay
