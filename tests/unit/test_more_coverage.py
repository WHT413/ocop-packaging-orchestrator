from pathlib import Path

import pytest

from ocop_pack.domain.dieline import DielineSpec, load_dieline
from ocop_pack.domain.geometry import BoundingBox
from ocop_pack.engine.logo_layout import validate_logo_integrity
from ocop_pack.engine.scoring import score_results
from ocop_pack.infrastructure.config import DEFAULT_DB_URL, DEFAULT_RUNS_DIR
from ocop_pack.infrastructure.logging import configure_logging
from ocop_pack.infrastructure.persistence.sqlite import init_db, make_engine, session_factory
from ocop_pack.infrastructure.storage.local import LocalArtifactStorage
from ocop_pack.services.layout_service import generate_valid_candidates
from ocop_pack.services.validation_service import file_sha256


def test_geometry_extra_ops():
    box = BoundingBox(x_mm=5, y_mm=5, width_mm=10, height_mm=10)
    assert box.translate(1, 2).x_mm == 6
    assert box.scale_from_center(0.5).width_mm == 5
    assert box.distance_to(BoundingBox(x_mm=30, y_mm=5, width_mm=2, height_mm=2)) > 0
    assert box.clamp_to(BoundingBox(x_mm=0, y_mm=0, width_mm=8, height_mm=8)).right <= 8


def test_invalid_dielines():
    with pytest.raises(ValueError):
        load_dieline("BAD")
    with pytest.raises(ValueError):
        DielineSpec(
            size_id="OCOP_130X150",
            version="x",
            width_mm=10,
            height_mm=10,
            vertical_folds_x_mm=[8, 2],
            horizontal_folds_y_mm=[1, 9],
            fold_exclusion_mm=1,
        )


def test_storage_and_logo(example_project, tmp_path: Path):
    storage = LocalArtifactStorage(tmp_path)
    rel, digest = storage.atomic_write("run1", "final/a.txt", b"abc")
    assert rel.endswith("a.txt") and digest == file_sha256(tmp_path / rel)
    with pytest.raises(ValueError):
        storage.atomic_write("run1", "../bad.txt", b"x")
    info = validate_logo_integrity(example_project.branding.logos[0].path, 20, 10)
    assert info["preserved"] is True


def test_service_config_logging_sqlite(example_project):
    assert DEFAULT_DB_URL.startswith("sqlite") and str(DEFAULT_RUNS_DIR) == "runs"
    configure_logging()
    d = load_dieline(example_project.packaging.size_id)
    assert generate_valid_candidates(example_project, d)
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    assert session_factory(engine)


def test_scoring(example_project):
    d = load_dieline(example_project.packaging.size_id)
    results = generate_valid_candidates(example_project, d)
    assert results
    from ocop_pack.engine.constraints import evaluate_candidate

    assert score_results(evaluate_candidate(example_project, d, results[0])) > 0
