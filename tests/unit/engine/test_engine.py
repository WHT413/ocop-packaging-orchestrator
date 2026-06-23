from pathlib import Path

import pytest

from ocop_pack.domain.dieline import load_dieline
from ocop_pack.domain.geometry import BoundingBox
from ocop_pack.engine.candidate_generator import generate_candidates
from ocop_pack.engine.constraints import candidate_passed, evaluate_candidate
from ocop_pack.engine.ocop_lockup import compose_ocop_lockup
from ocop_pack.engine.qr import decode_qr, generate_qr
from ocop_pack.engine.renderer import mm_to_px
from ocop_pack.engine.text_fit import FontSpec, fit_text


def test_candidates_deterministic(example_project):
    d = load_dieline(example_project.packaging.size_id)
    a = generate_candidates(example_project, d, seed=7)
    b = generate_candidates(example_project, d, seed=7)
    assert 12 <= len(a) <= 24
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
