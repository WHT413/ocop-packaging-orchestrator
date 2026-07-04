from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ocop_pack.orchestration.budgets import BudgetPolicy
from ocop_pack.orchestration.errors import WorkflowException
from ocop_pack.orchestration.runner import WorkflowRunner, artifact_hash
from ocop_pack.orchestration.status import RunStatus

PROJECT = Path("examples/projects/tea_basic/project.yaml")


def test_phase2_happy_path(tmp_path: Path) -> None:
    runner = WorkflowRunner(tmp_path)
    state = runner.start(PROJECT, "run_happy")
    assert state["status"] == RunStatus.WAITING_APPROVAL
    state = runner.approve("run_happy", state["selected_candidate_id"] or "")
    assert state["status"] == RunStatus.EXPORTED
    assert Path(state["final_png_ref"] or "").exists()
    assert Path(state["final_pdf_ref"] or "").exists()
    qa_report = Path(state["qa_report_ref"] or "")
    assert qa_report.exists()
    qa = json.loads(qa_report.read_text(encoding="utf-8"))
    assert qa["passed"] is True
    manifest = json.loads((tmp_path / "run_happy" / "run_manifest.json").read_text())
    exported_state = manifest["state"]
    assert exported_state["final_png_ref"] == state["final_png_ref"]
    assert exported_state["final_pdf_ref"] == state["final_pdf_ref"]


def test_phase2_rejection_stops_final_render(tmp_path: Path) -> None:
    runner = WorkflowRunner(tmp_path)
    state = runner.start(PROJECT, "run_reject")
    state = runner.reject("run_reject", "not acceptable")
    assert state["status"] == RunStatus.REJECTED
    assert not (tmp_path / "run_reject" / "final" / "packaging.png").exists()


def test_invalid_candidate_approval(tmp_path: Path) -> None:
    runner = WorkflowRunner(tmp_path)
    runner.start(PROJECT, "run_bad_candidate")
    with pytest.raises(WorkflowException):
        runner.approve("run_bad_candidate", "C999")


def test_budget_exceeded_for_candidates(tmp_path: Path) -> None:
    runner = WorkflowRunner(tmp_path, BudgetPolicy(max_candidates=0))
    with pytest.raises(WorkflowException):
        runner.start(PROJECT, "run_budget")


def test_project_change_after_approval_invalidates(tmp_path: Path) -> None:
    project_copy = tmp_path / "project.yaml"
    shutil.copytree(PROJECT.parent / "assets", tmp_path / "assets")
    shutil.copyfile(PROJECT, project_copy)
    runner = WorkflowRunner(tmp_path)
    state = runner.start(project_copy, "run_project_change")
    approval_state = runner.load_state("run_project_change")
    runner.approve("run_project_change", state["selected_candidate_id"] or "")
    text = project_copy.read_text(encoding="utf-8")
    project_copy.write_text(
        text.replace("Tra thao moc OCOP", "Tra thao moc OCOP Changed"), encoding="utf-8"
    )
    approval_state = runner.load_state("run_project_change")
    approval_state["project"] = None
    with pytest.raises(WorkflowException):
        runner._validate_approval(approval_state)


@pytest.mark.parametrize(
    "node",
    [
        "validate_input",
        "generate_layout_candidates",
        "render_candidate_previews",
        "run_draft_qa",
        "render_final_outputs",
        "run_final_qa",
        "export_bundle",
    ],
)
def test_crash_resume_no_duplicate_side_effects(tmp_path: Path, node: str) -> None:
    run_id = f"run_crash_{node}"
    runner = WorkflowRunner(tmp_path)
    try:
        state = runner.start(PROJECT, run_id, crash_after=node)
        if state["status"] == RunStatus.WAITING_APPROVAL:
            state = runner.approve(run_id, state["selected_candidate_id"] or "", approved_by="test")
    except RuntimeError:
        state = runner.load_state(run_id)
    if state["status"] == RunStatus.WAITING_APPROVAL:
        try:
            state = runner.approve(run_id, state["selected_candidate_id"] or "", approved_by="test")
        except RuntimeError:
            state = runner.load_state(run_id)
    while state["status"] != RunStatus.EXPORTED:
        state = runner.resume(run_id)
        if state["status"] == RunStatus.WAITING_APPROVAL:
            state = runner.approve(run_id, state["selected_candidate_id"] or "", approved_by="test")
    png_hash = artifact_hash(state["final_png_ref"])
    pdf_hash = artifact_hash(state["final_pdf_ref"])
    resumed = runner.resume(run_id)
    assert resumed["status"] == RunStatus.EXPORTED
    assert artifact_hash(resumed["final_png_ref"]) == png_hash
    assert artifact_hash(resumed["final_pdf_ref"]) == pdf_hash
    assert len(list((tmp_path / run_id / "approval").glob("approval.json"))) <= 1
