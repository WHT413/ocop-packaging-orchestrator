from pathlib import Path

import pytest

from ocop_pack.cli.app import _audit_run_dir, _cleanup_run_dir, _render_editable_layout
from ocop_pack.domain.dieline import DielineSpec, load_dieline
from ocop_pack.domain.geometry import BoundingBox
from ocop_pack.engine.candidate_generator import generate_candidates
from ocop_pack.engine.logo_layout import validate_logo_integrity
from ocop_pack.engine.scoring import score_results
from ocop_pack.engine.typography import source_text
from ocop_pack.infrastructure.config import DEFAULT_DB_URL, DEFAULT_RUNS_DIR
from ocop_pack.infrastructure.logging import configure_logging
from ocop_pack.infrastructure.persistence.sqlite import init_db, make_engine, session_factory
from ocop_pack.infrastructure.storage.local import LocalArtifactStorage
from ocop_pack.services.layout_service import generate_valid_candidates
from ocop_pack.services.validation_service import file_sha256, load_project


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


@pytest.mark.parametrize(
    "project_yaml",
    [
        "examples/projects/tea_basic/project.yaml",
        "examples/projects/honey_basic/project.yaml",
        "examples/projects/matcha_basic/project.yaml",
        "examples/projects/ginger_honey_basic/project.yaml",
        "examples/projects/local_jam_1star_basic/project.yaml",
        "examples/projects/banana_chip_2star_basic/project.yaml",
        "examples/projects/coffee_4star_basic/project.yaml",
        "examples/projects/lotus_seed_5star_basic/project.yaml",
    ],
)
def test_example_projects_generate_valid_layouts(project_yaml: str):
    project = load_project(Path(project_yaml))
    dieline = load_dieline(project.packaging.size_id)

    candidates = generate_valid_candidates(project, dieline)

    assert candidates


def test_candidate_style_controls_vary_by_seed(example_project):
    dieline = load_dieline(example_project.packaging.size_id)

    first = generate_candidates(example_project, dieline, seed=1)[0]
    second = generate_candidates(example_project, dieline, seed=2)[0]

    assert (
        first.metadata["frame_style"],
        first.metadata["font_mood"],
        first.metadata["contrast_style"],
    ) != (
        second.metadata["frame_style"],
        second.metadata["font_mood"],
        second.metadata["contrast_style"],
    )


def test_ingredient_panel_uses_label_like_sections(example_project):
    details = source_text(example_project, "product.details")

    assert "THANH PHAN:" in details
    assert "HUONG DAN SU DUNG:" in details
    assert "HUONG DAN BAO QUAN:" in details
    assert example_project.product.ingredients[:24] in details


def test_traceability_codes_are_opt_in(example_project):
    project = example_project.model_copy(
        update={
            "packaging": example_project.packaging.model_copy(
                update={"show_qr": False, "show_barcode": False}
            )
        }
    )
    dieline = load_dieline(project.packaging.size_id)
    candidate = generate_candidates(project, dieline)[0]

    assert not any(e.kind == "qr" for e in candidate.elements)
    assert not any(e.source_ref == "packaging.barcode" for e in candidate.elements)


def test_scoring(example_project):
    d = load_dieline(example_project.packaging.size_id)
    results = generate_valid_candidates(example_project, d)
    assert results
    from ocop_pack.engine.constraints import evaluate_candidate

    assert score_results(evaluate_candidate(example_project, d, results[0])) > 0


def test_cleanup_run_dir_keeps_final_and_skips_unexported(tmp_path: Path):
    exported = tmp_path / "exported"
    waiting = tmp_path / "waiting"
    for run_dir, status in [(exported, "EXPORTED"), (waiting, "WAITING_APPROVAL")]:
        (run_dir / "final").mkdir(parents=True)
        (run_dir / "previews").mkdir()
        (run_dir / "run_manifest.json").write_text(
            f'{{"state": {{"status": "{status}"}}}}', encoding="utf-8"
        )

    assert _cleanup_run_dir(waiting, delete=True) == []
    removed = _cleanup_run_dir(exported, delete=True)

    assert exported / "previews" in removed
    assert not (exported / "previews").exists()
    assert (exported / "final").exists()
    assert (waiting / "previews").exists()


def test_render_editable_layout_outputs_png_pdf_and_qa(tmp_path: Path):
    from ocop_pack.orchestration.runner import WorkflowRunner

    runner = WorkflowRunner(runs_root=tmp_path)
    state = runner.start(Path("examples/projects/tea_basic/project.yaml"), "editable_cli")
    approved = runner.approve("editable_cli", state["selected_candidate_id"] or "", "test")

    result = _render_editable_layout(
        Path(approved["artifact_refs"]["final:editable_layout"]),
        Path("examples/projects/tea_basic/project.yaml"),
        tmp_path / "edited",
    )

    assert Path(result["png"]).exists()
    assert Path(result["pdf"]).exists()
    assert Path(result["svg"]).exists()
    assert Path(result["qa"]).exists()


def test_audit_run_dir_flags_missing_final_and_hash_mismatch(tmp_path: Path):
    run_dir = tmp_path / "exported"
    final = run_dir / "final"
    final.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text(
        '{"state": {"status": "EXPORTED"}}', encoding="utf-8"
    )
    (final / "packaging.png").write_text("png", encoding="utf-8")
    (final / "packaging.pdf").write_text("pdf", encoding="utf-8")
    (final / "packaging.svg").write_text("svg", encoding="utf-8")
    (final / "editable_layout.json").write_text("{}", encoding="utf-8")
    (final / "print_spec.json").write_text("{}", encoding="utf-8")
    (final / "packaging.manifest.json").write_text(
        '{"png_hash": "bad"}', encoding="utf-8"
    )

    report = _audit_run_dir(run_dir)

    assert report["final_complete"] is True
    assert "HASH_MISMATCH:packaging.png" in report["issues"]


def test_audit_run_dir_flags_exported_missing_final_files(tmp_path: Path):
    run_dir = tmp_path / "missing"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text(
        '{"state": {"status": "EXPORTED"}}', encoding="utf-8"
    )

    report = _audit_run_dir(run_dir)

    assert report["final_complete"] is False
    assert "EXPORTED_RUN_MISSING_FINAL_FILES" in report["issues"]
