from pathlib import Path

from ocop_pack.domain.dieline import load_dieline
from ocop_pack.domain.layout import LayoutManifest
from ocop_pack.domain.runs import RunRecord
from ocop_pack.engine.candidate_generator import generate_candidates
from ocop_pack.engine.constraints import candidate_passed, evaluate_candidate
from ocop_pack.infrastructure.persistence.repositories import (
    SqlCandidateRepository,
    SqlRunRepository,
)
from ocop_pack.infrastructure.persistence.session import init_db, make_engine, session_factory
from ocop_pack.services.qa_service import qa_candidate
from ocop_pack.services.render_service import render_manifest
from ocop_pack.services.validation_service import project_hash


def test_full_pipeline(example_project, tmp_path: Path):
    d = load_dieline(example_project.packaging.size_id)
    cand = next(
        c
        for c in generate_candidates(example_project, d)
        if candidate_passed(evaluate_candidate(example_project, d, c))
    )
    manifest = LayoutManifest(
        run_id="run_test",
        project_id=example_project.project_id,
        dieline_version=d.version,
        candidate=cand,
    )
    png, pdf, _ = render_manifest(manifest, example_project, d, tmp_path)
    assert png.exists() and pdf.exists()
    report = qa_candidate("run_test", example_project, d, cand, png)
    assert report.results
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    with session_factory(engine)() as s:
        SqlRunRepository(s).create(
            RunRecord(
                run_id="run_test",
                project_id=example_project.project_id,
                input_hash=project_hash(example_project),
                dieline_version=d.version,
            )
        )
        SqlCandidateRepository(s).save_many("run_test", [cand])
        assert (
            SqlCandidateRepository(s).list_by_run("run_test")[0].candidate_id == cand.candidate_id
        )
