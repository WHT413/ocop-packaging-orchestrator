from pathlib import Path

import pytest
from PIL import Image

from ocop_pack.domain.dieline import load_dieline
from ocop_pack.domain.geometry import BoundingBox
from ocop_pack.engine.candidate_generator import generate_candidates
from ocop_pack.engine.constraints import candidate_passed, evaluate_candidate
from ocop_pack.engine.ocop_lockup import compose_ocop_lockup
from ocop_pack.engine.qr import (
    QR_POLICY_VERSION,
    decode_qr,
    generate_qr,
    qr_render_metadata,
    render_qr_square,
)
from ocop_pack.engine.renderer import mm_to_px, render_png
from ocop_pack.engine.scene import Scene, SceneElement
from ocop_pack.engine.text_fit import FontSpec, fit_text


def test_candidates_deterministic(example_project):
    d = load_dieline(example_project.packaging.size_id)
    a = generate_candidates(example_project, d, seed=7)
    b = generate_candidates(example_project, d, seed=7)
    assert 3 <= len(a) <= 6
    assert [c.model_dump() for c in a] == [c.model_dump() for c in b]
    assert any(candidate_passed(evaluate_candidate(example_project, d, c)) for c in a)


def test_text_qr_star(tmp_path: Path):
    assert fit_text(
        "Tieng Viet co dau",
        BoundingBox(x_mm=0, y_mm=0, width_mm=50, height_mm=20),
        FontSpec(),
        6,
        16,
    ).fits
    qr = tmp_path / "qr.png"
    generate_qr("https://example.com").save(qr)
    assert decode_qr(qr) == "https://example.com"
    with pytest.raises(ValueError):
        compose_ocop_lockup("x", 6, BoundingBox(x_mm=0, y_mm=0, width_mm=10, height_mm=10))


def test_png_dimensions():
    assert mm_to_px(25.4, 100) == 100


def test_generated_qr_candidates_are_square_panel_safe(example_project):
    dieline = load_dieline(example_project.packaging.size_id)
    right = {p.name: p.bbox_mm for p in dieline.panels()}["right_panel"]
    canvas = dieline.canvas()
    for candidate in generate_candidates(example_project, dieline):
        qr = next(e for e in candidate.elements if e.kind == "qr")
        assert qr.bbox_mm.width_mm == pytest.approx(qr.bbox_mm.height_mm)
        assert qr.bbox_mm.width_mm >= 12
        assert right.contains(qr.bbox_mm)
        assert not canvas.crosses_vertical_fold(qr.bbox_mm)
        assert not canvas.crosses_horizontal_fold_band(qr.bbox_mm)
        assert qr.metadata["qr_policy_version"] == QR_POLICY_VERSION
        assert qr.metadata["effective_size_mm"] == pytest.approx(qr.bbox_mm.width_mm)


def test_legacy_non_square_qr_renders_centered_without_smoothing(example_project, tmp_path: Path):
    bbox = BoundingBox(x_mm=10, y_mm=10, width_mm=30, height_mm=18)
    scene = Scene(
        run_id="r",
        project_id="p",
        width_mm=60,
        height_mm=50,
        elements=[
            SceneElement(
                element_id="qr", kind="qr", source_ref="packaging.qr_payload", bbox_mm=bbox
            )
        ],
    )
    out = render_png(scene, example_project, tmp_path / "legacy.png", dpi=254)
    assert decode_qr(out) == example_project.packaging.qr_payload
    with Image.open(out) as img:
        px = img.convert("RGB")
        x0 = mm_to_px(bbox.x_mm, 254)
        y0 = mm_to_px(bbox.y_mm, 254)
        w = mm_to_px(bbox.width_mm, 254) - mm_to_px(0, 254)
        h = mm_to_px(bbox.height_mm, 254) - mm_to_px(0, 254)
        side = min(w, h)
        left_pad = (w - side) // 2
        assert px.getpixel((x0 + 1, y0 + 1)) == (255, 255, 255)
        assert px.getpixel((x0 + left_pad + 1, y0 + 1)) == (255, 255, 255)
        colors = set(px.crop((x0 + left_pad, y0, x0 + left_pad + side, y0 + side)).getdata())
        assert colors <= {(0, 0, 0), (255, 255, 255)}


def test_qr_render_fails_closed_when_too_small():
    with pytest.raises(ValueError, match="too small"):
        qr_render_metadata(
            "https://example.com", BoundingBox(x_mm=0, y_mm=0, width_mm=10, height_mm=20)
        )
    with pytest.raises(ValueError, match="too small"):
        render_qr_square("https://example.com", (8, 40))
