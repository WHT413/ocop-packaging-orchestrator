from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, cast

from ocop_pack.domain.dieline import load_dieline
from ocop_pack.domain.layout import LayoutCandidate, LayoutManifest
from ocop_pack.domain.project import ProjectSpec
from ocop_pack.domain.qa import QAReport
from ocop_pack.engine.candidate_generator import generate_candidates
from ocop_pack.engine.constraints import candidate_passed, evaluate_candidate
from ocop_pack.observability.events import EventLog
from ocop_pack.orchestration.budgets import BudgetPolicy, BudgetTracker
from ocop_pack.orchestration.checkpoint import LocalCheckpointStore
from ocop_pack.orchestration.errors import WorkflowError, WorkflowException
from ocop_pack.orchestration.idempotency import file_hash, mark_completed, stable_hash
from ocop_pack.orchestration.state import ApprovalRecord, PackagingState, initial_state
from ocop_pack.orchestration.status import RunStatus, assert_transition
from ocop_pack.providers.mocks.fixture_artwork_provider import FixtureArtworkProvider
from ocop_pack.providers.mocks.mock_planner import MockDesignPlanner
from ocop_pack.services.qa_service import qa_candidate
from ocop_pack.services.render_service import render_manifest
from ocop_pack.services.validation_service import load_project, project_hash
from ocop_pack.storage.local_artifact_store import LocalArtifactStore

SIDE_EFFECT_NODES = {
    "validate_input",
    "prepare_design_inputs",
    "load_fixture_artwork",
    "generate_layout_candidates",
    "render_candidate_previews",
    "run_draft_qa",
    "await_human_approval",
    "render_final_outputs",
    "run_final_qa",
    "export_bundle",
}


class WorkflowRunner:
    def __init__(
        self,
        runs_root: Path = Path("runs"),
        budget_policy: BudgetPolicy | None = None,
    ) -> None:
        self.store = LocalArtifactStore(runs_root)
        self.checkpoints = LocalCheckpointStore(runs_root)
        self.events = EventLog(runs_root)
        self.budget = BudgetTracker(budget_policy or BudgetPolicy())

    def start(
        self, project_path: Path, run_id: str, crash_after: str | None = None
    ) -> PackagingState:
        state = initial_state(run_id, str(project_path))
        return self._drive(state, crash_after=crash_after)

    def resume(self, run_id: str, crash_after: str | None = None) -> PackagingState:
        state = self.load_state(run_id)
        self.events.append(run_id, state["thread_id"], "resume", "resume", str(state["status"]))
        return self._drive(state, crash_after=crash_after)

    def load_state(self, run_id: str) -> PackagingState:
        raw = self.checkpoints.load(run_id)
        if raw is None:
            manifest = self.store.path(run_id, "run_manifest.json")
            if not manifest.exists():
                raise WorkflowException(
                    WorkflowError(code="RUN_NOT_FOUND", message="run not found")
                )
            loaded = json.loads(manifest.read_text(encoding="utf-8"))
            raw = cast(dict[str, Any], loaded["state"])
        state = initial_state(raw["run_id"], raw["project_path"], raw["thread_id"])
        for key, value in raw.items():
            state[key] = value  # type: ignore[literal-required]
        state["status"] = RunStatus(raw["status"])
        state["approval"] = ApprovalRecord(**raw["approval"]) if raw.get("approval") else None
        state["errors"] = [WorkflowError(**e) for e in raw.get("errors", [])]
        if state["project_path"]:
            state["project"] = load_project(Path(state["project_path"]))
        return state

    def approve(self, run_id: str, candidate_id: str, approved_by: str = "cli") -> PackagingState:
        state = self.load_state(run_id)
        if state["status"] != RunStatus.WAITING_APPROVAL:
            raise WorkflowException(
                WorkflowError(code="INVALID_STATE", message="run is not waiting approval")
            )
        candidates = self._load_candidates(state)
        candidate = next((c for c in candidates if c.candidate_id == candidate_id), None)
        if candidate is None:
            raise WorkflowException(
                WorkflowError(code="INVALID_CANDIDATE", message="candidate not found")
            )
        cand_hash = stable_hash(candidate.model_dump(mode="json"))
        state["selected_candidate_id"] = candidate_id
        state["selected_candidate_hash"] = cand_hash
        approval = ApprovalRecord(
            run_id=run_id,
            candidate_id=candidate_id,
            candidate_hash=cand_hash,
            project_hash=state["project_hash"],
            approved_by=approved_by,
            decision="approve",
        )
        state["approval"] = approval
        self.store.write_json_once(
            run_id, "approval/approval.json", approval.model_dump(mode="json")
        )
        self._transition(state, RunStatus.APPROVED, "await_human_approval")
        return self._drive(state)

    def reject(self, run_id: str, reason: str, approved_by: str = "cli") -> PackagingState:
        state = self.load_state(run_id)
        if state["status"] != RunStatus.WAITING_APPROVAL:
            raise WorkflowException(
                WorkflowError(code="INVALID_STATE", message="run is not waiting approval")
            )
        approval = ApprovalRecord(
            run_id=run_id,
            candidate_id=state["selected_candidate_id"] or "",
            candidate_hash=state["selected_candidate_hash"] or "",
            project_hash=state["project_hash"],
            approved_by=approved_by,
            decision="reject",
            reason=reason,
        )
        state["approval"] = approval
        self.store.write_json_once(
            run_id, "approval/approval.json", approval.model_dump(mode="json")
        )
        self._transition(state, RunStatus.REJECTED, "await_human_approval")
        return state

    def _drive(self, state: PackagingState, crash_after: str | None = None) -> PackagingState:
        while state["status"] not in {
            RunStatus.WAITING_APPROVAL,
            RunStatus.EXPORTED,
            RunStatus.REJECTED,
        }:
            node = self._next_node(state)
            getattr(self, f"_{node}")(state)
            self._checkpoint(state, node)
            if crash_after == node:
                self.events.append(
                    state["run_id"],
                    state["thread_id"],
                    node,
                    "simulated_crash",
                    str(state["status"]),
                )
                raise RuntimeError(f"simulated crash after {node}")
        return state

    def _next_node(self, state: PackagingState) -> str:
        return {
            RunStatus.CREATED: "validate_input",
            RunStatus.INPUT_VALIDATED: "prepare_design_inputs",
            RunStatus.DESIGN_INPUTS_READY: "load_fixture_artwork",
            RunStatus.ARTWORK_READY: "generate_layout_candidates",
            RunStatus.CANDIDATES_READY: "render_candidate_previews",
            RunStatus.PREVIEWS_READY: "run_draft_qa",
            RunStatus.DRAFT_QA_PASSED: "await_human_approval",
            RunStatus.APPROVED: "render_final_outputs",
            RunStatus.FINAL_RENDERED: "run_final_qa",
            RunStatus.FINAL_QA_PASSED: "export_bundle",
        }[state["status"]]

    def _validate_input(self, state: PackagingState) -> None:
        project = load_project(Path(state["project_path"]))
        state["project"] = project
        state["project_hash"] = project_hash(project)
        self.store.copy_once(
            state["run_id"], Path(state["project_path"]), "input/project.snapshot.yaml"
        )
        self._transition(state, RunStatus.INPUT_VALIDATED, "validate_input")

    def _prepare_design_inputs(self, state: PackagingState) -> None:
        self.budget.check(state, "prepare_design_inputs")
        plan = MockDesignPlanner().create_plan(self._project(state))
        state["design_plan_ref"] = self.store.write_json_once(
            state["run_id"], "mock/design_plan.json", plan
        )
        self._transition(state, RunStatus.DESIGN_INPUTS_READY, "prepare_design_inputs")

    def _load_fixture_artwork(self, state: PackagingState) -> None:
        artwork = FixtureArtworkProvider().load_artwork(self._project(state))
        ref = self.store.write_json_once(state["run_id"], "mock/artwork_manifest.json", artwork)
        state["artwork_refs"] = [ref]
        self.store.write_json_once(state["run_id"], "input/asset_manifest.json", artwork)
        self._transition(state, RunStatus.ARTWORK_READY, "load_fixture_artwork")

    def _generate_layout_candidates(self, state: PackagingState) -> None:
        project = self._project(state)
        dieline = load_dieline(project.packaging.size_id)
        candidates = [
            c
            for c in generate_candidates(project, dieline)
            if candidate_passed(evaluate_candidate(project, dieline, c))
        ]
        self.budget.check(state, "generate_layout_candidates", len(candidates))
        if not candidates:
            self._transition(state, RunStatus.FAILED_LAYOUT, "generate_layout_candidates")
            return
        ref = self.store.write_json_once(
            state["run_id"],
            "candidates/candidates.json",
            [c.model_dump(mode="json") for c in candidates],
        )
        state["candidate_refs"] = [ref]
        self._transition(state, RunStatus.CANDIDATES_READY, "generate_layout_candidates")

    def _render_candidate_previews(self, state: PackagingState) -> None:
        project = self._project(state)
        candidate = self._load_candidates(state)[0]
        state["selected_candidate_id"] = candidate.candidate_id
        state["selected_candidate_hash"] = stable_hash(candidate.model_dump(mode="json"))
        dieline = load_dieline(project.packaging.size_id)
        temp_dir = self.store.run_dir(state["run_id"])
        render_manifest(
            LayoutManifest(
                run_id=state["run_id"],
                project_id=project.project_id,
                dieline_version=dieline.version,
                candidate=candidate,
            ),
            project,
            dieline,
            temp_dir,
        )
        final_png = temp_dir / "final" / "final_preview.png"
        selected = self.store.path(state["run_id"], "previews/selected.png")
        sheet = self.store.path(state["run_id"], "previews/contact_sheet.png")
        selected.parent.mkdir(parents=True, exist_ok=True)
        if not selected.exists():
            shutil.copyfile(final_png, selected)
        if not sheet.exists():
            shutil.copyfile(final_png, sheet)
        state["preview_refs"] = [str(sheet), str(selected)]
        self._transition(state, RunStatus.PREVIEWS_READY, "render_candidate_previews")

    def _run_draft_qa(self, state: PackagingState) -> None:
        report = self._qa(state, Path(state["preview_refs"][-1]))
        state["qa_report_ref"] = self.store.write_json_once(
            state["run_id"], "qa/draft_qa_report.json", report.model_dump(mode="json")
        )
        self._transition(
            state,
            RunStatus.DRAFT_QA_PASSED if report.passed else RunStatus.FAILED_QA,
            "run_draft_qa",
        )

    def _await_human_approval(self, state: PackagingState) -> None:
        self._transition(state, RunStatus.WAITING_APPROVAL, "await_human_approval")

    def _render_final_outputs(self, state: PackagingState) -> None:
        self._validate_approval(state)
        project = self._project(state)
        candidate = self._selected_candidate(state)
        dieline = load_dieline(project.packaging.size_id)
        png, pdf, _ = render_manifest(
            LayoutManifest(
                run_id=state["run_id"],
                project_id=project.project_id,
                dieline_version=dieline.version,
                candidate=candidate,
            ),
            project,
            dieline,
            self.store.run_dir(state["run_id"]),
        )
        final_png = self.store.path(state["run_id"], "final/packaging.png")
        final_pdf = self.store.path(state["run_id"], "final/packaging.pdf")
        if not final_png.exists():
            shutil.copyfile(png, final_png)
        if not final_pdf.exists():
            shutil.copyfile(pdf, final_pdf)
        state["final_png_ref"] = str(final_png)
        state["final_pdf_ref"] = str(final_pdf)
        self._transition(state, RunStatus.FINAL_RENDERED, "render_final_outputs")

    def _run_final_qa(self, state: PackagingState) -> None:
        report = self._qa(state, Path(state["final_png_ref"] or ""))
        state["qa_report_ref"] = self.store.write_json_once(
            state["run_id"], "qa/qa_report.json", report.model_dump(mode="json")
        )
        self._transition(
            state,
            RunStatus.FINAL_QA_PASSED if report.passed else RunStatus.FAILED_QA,
            "run_final_qa",
        )

    def _export_bundle(self, state: PackagingState) -> None:
        self._validate_approval(state)
        manifest = {
            "state": self._serializable(state),
            "final": {"png": state["final_png_ref"], "pdf": state["final_pdf_ref"]},
        }
        self.store.write_json_once(state["run_id"], "run_manifest.json", manifest)
        self._transition(state, RunStatus.EXPORTED, "export_bundle")

    def _qa(self, state: PackagingState, png: Path) -> QAReport:
        project = self._project(state)
        return qa_candidate(
            state["run_id"],
            project,
            load_dieline(project.packaging.size_id),
            self._selected_candidate(state),
            png,
        )

    def _project(self, state: PackagingState) -> ProjectSpec:
        if state["project"] is None:
            state["project"] = load_project(Path(state["project_path"]))
        project = state["project"]
        if project is None:
            raise WorkflowException(
                WorkflowError(code="PROJECT_NOT_LOADED", message="project not loaded")
            )
        return project

    def _load_candidates(self, state: PackagingState) -> list[LayoutCandidate]:
        path = (
            Path(state["candidate_refs"][0])
            if state["candidate_refs"]
            else self.store.path(state["run_id"], "candidates/candidates.json")
        )
        return [LayoutCandidate(**item) for item in json.loads(path.read_text(encoding="utf-8"))]

    def _selected_candidate(self, state: PackagingState) -> LayoutCandidate:
        return next(
            c
            for c in self._load_candidates(state)
            if c.candidate_id == state["selected_candidate_id"]
        )

    def _validate_approval(self, state: PackagingState) -> None:
        approval = state["approval"]
        if approval is None or approval.decision != "approve":
            raise WorkflowException(
                WorkflowError(code="APPROVAL_REQUIRED", message="approval required")
            )
        project = self._project(state)
        if approval.project_hash != project_hash(project):
            raise WorkflowException(
                WorkflowError(code="APPROVAL_INVALID", message="project hash changed")
            )
        if approval.candidate_hash != stable_hash(
            self._selected_candidate(state).model_dump(mode="json")
        ):
            raise WorkflowException(
                WorkflowError(code="APPROVAL_INVALID", message="candidate hash changed")
            )

    def _transition(self, state: PackagingState, next_status: RunStatus, node: str) -> None:
        assert_transition(state["status"], next_status)
        state["status"] = next_status
        state["completed_nodes"] = mark_completed(state["completed_nodes"], node)
        self.events.append(state["run_id"], state["thread_id"], node, "completed", str(next_status))

    def _checkpoint(self, state: PackagingState, node: str) -> None:
        self.checkpoints.save(state["run_id"], state)
        self.store.write_json_once(
            state["run_id"], "run_manifest.json", {"state": self._serializable(state)}
        )
        if node in SIDE_EFFECT_NODES:
            state["artifact_refs"][f"checkpoint:{node}"] = str(
                self.store.path(state["run_id"], "checkpoints/state.json")
            )

    def _serializable(self, state: PackagingState) -> dict[str, object]:
        return {
            key: value.model_dump(mode="json") if hasattr(value, "model_dump") else value
            for key, value in state.items()
            if key != "project"
        }


def artifact_hash(path: str | None) -> str | None:
    return file_hash(Path(path)) if path else None
