from __future__ import annotations

import json
import shutil
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from ocop_pack.agents.design_planner.agent import (
    build_planner_input,
    default_prompts,
    planner_input_hash,
    planner_prompt_hash,
)
from ocop_pack.agents.design_planner.validator import validate_immutable_facts
from ocop_pack.agents.visual_critic.guard import CriticGuardContext, validate_critic_decision
from ocop_pack.agents.visual_critic.prompt_registry import default_prompts as critic_prompts
from ocop_pack.agents.visual_critic.rubric import RUBRIC_VERSION
from ocop_pack.application.ports.artwork_provider import ArtworkRequest, ArtworkResult
from ocop_pack.application.ports.artwork_revision import ArtworkRevisionRequest
from ocop_pack.application.ports.planner import PlannerRequest
from ocop_pack.application.ports.vision_critic import CriticRequest
from ocop_pack.cache.cache_keys import critic_cache_key, revision_cache_key, stable_cache_key
from ocop_pack.domain.dieline import load_dieline
from ocop_pack.domain.layout import LayoutCandidate, LayoutManifest
from ocop_pack.domain.project import ProjectSpec
from ocop_pack.domain.qa import QAReport
from ocop_pack.engine.candidate_generator import attach_artwork_layers, generate_candidates
from ocop_pack.engine.constraints import candidate_passed, evaluate_candidate
from ocop_pack.engine.contact_sheet import (
    CONTACT_SHEET_RENDERER_VERSION,
    render_contact_sheet,
    select_top_k,
)
from ocop_pack.engine.renderer import RenderAssetError
from ocop_pack.infrastructure.config import (
    ImageSettings,
    PlannerSettings,
    RevisionSettings,
    VisionSettings,
    WorkflowBudgetSettings,
)
from ocop_pack.observability.events import EventLog
from ocop_pack.orchestration.budgets import BudgetPolicy, BudgetTracker
from ocop_pack.orchestration.checkpoint import LocalCheckpointStore
from ocop_pack.orchestration.errors import WorkflowError, WorkflowException
from ocop_pack.orchestration.idempotency import file_hash, mark_completed, stable_hash
from ocop_pack.orchestration.state import ApprovalRecord, PackagingState, initial_state
from ocop_pack.orchestration.status import TERMINAL_STATUSES, RunStatus, assert_transition
from ocop_pack.provenance.models import ProviderContext
from ocop_pack.providers.common.errors import (
    ProviderConfigurationError,
    ProviderError,
    ProviderSchemaError,
)
from ocop_pack.providers.common.retry import RetryPolicy, run_with_retry
from ocop_pack.providers.image.fixture import FixtureArtworkProvider
from ocop_pack.providers.image.openai_compatible import OpenAICompatibleImageProvider
from ocop_pack.providers.planner.mock import MockPlannerProvider
from ocop_pack.providers.planner.openai_compatible import OpenAICompatiblePlannerProvider
from ocop_pack.providers.revision.fixture import FixtureArtworkRevisionProvider
from ocop_pack.providers.vision.mock import MockVisualCriticProvider
from ocop_pack.providers.vision.openai_compatible import OpenAICompatibleVisionCriticProvider
from ocop_pack.schemas.design_planner import DesignPlan
from ocop_pack.services.qa_service import qa_candidate
from ocop_pack.services.render_service import PNG_RENDER_DPI, render_manifest
from ocop_pack.services.svg_service import render_svg_manifest
from ocop_pack.services.validation_service import load_project, project_hash
from ocop_pack.storage.local_artifact_store import LocalArtifactStore

SIDE_EFFECT_NODES = {
    "validate_input",
    "plan_design",
    "generate_artworks",
    "generate_layout_candidates",
    "render_candidate_previews",
    "prepare_contact_sheet",
    "visual_critic",
    "revise_artwork",
    "regenerate_after_revision",
    "run_draft_qa",
    "await_human_approval",
    "render_final_outputs",
    "run_final_qa",
    "export_bundle",
}

RENDERER_VERSION = "renderer.v3-readable-hires"

MANDATORY_ARTWORK_PROHIBITION = (
    "Artwork layer only. No text, no letters, no words, no numbers. "
    "No logos, no trademarks, no OCOP marks. No QR codes, no barcodes, "
    "no certification marks. No packaging mockup and no final label design. "
    "No medical or legal claims."
)


def build_artwork_prompt(
    concept_prompt: str,
    plan: DesignPlan | str,
    aspect_ratio: str,
) -> tuple[str, str]:
    if isinstance(plan, str):
        visual_direction = plan
        palette = "unspecified palette"
        motifs = "planner concept motifs"
        density = "balanced"
        negative_space = "balanced"
        strategy = "softened_full_background"
    else:
        visual_direction = plan.visual_direction
        palette = ", ".join(plan.palette)
        motifs = ", ".join(plan.decorative_motifs) or "safe decorative motifs"
        density = plan.artwork_density
        negative_space = plan.negative_space_intent
        strategy = plan.layout_intents[0].artwork_strategy
    positive = (
        f"{concept_prompt}. Visual direction: {visual_direction}. Palette intent: {palette}. "
        f"Motifs: {motifs}. Artwork density: {density}. Negative space: {negative_space}. "
        f"Artwork strategy: {strategy}. "
        f"Target aspect ratio: {aspect_ratio}. Decorative artwork only, suitable for softened "
        "backgrounds, framed hero regions, or panel-local strips in a deterministic layout."
    )
    return positive, MANDATORY_ARTWORK_PROHIBITION


class WorkflowRunner:
    def __init__(
        self,
        runs_root: Path = Path("runs"),
        budget_policy: BudgetPolicy | None = None,
        online: bool | None = None,
    ) -> None:
        self.store = LocalArtifactStore(runs_root)
        self.checkpoints = LocalCheckpointStore(runs_root)
        self.events = EventLog(runs_root)
        settings = WorkflowBudgetSettings()
        default_policy = BudgetPolicy(
            max_vision_calls=settings.max_vision_calls,
            max_revisions=settings.max_revision_count,
            max_image_edit_calls=settings.max_image_edit_calls,
        )
        self.budget = BudgetTracker(budget_policy or default_policy)
        # Library/test callers stay offline unless the CLI explicitly passes
        # ExecutionSettings().online. This keeps CI independent from local .env.
        self.online = False if online is None else online

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
            *TERMINAL_STATUSES,
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
            RunStatus.INPUT_VALIDATED: "plan_design",
            RunStatus.DESIGN_INPUTS_READY: "generate_artworks",
            RunStatus.ARTWORK_READY: "generate_layout_candidates",
            RunStatus.CANDIDATES_READY: "render_candidate_previews",
            RunStatus.PREVIEWS_READY: "prepare_contact_sheet",
            RunStatus.CONTACT_SHEET_READY: "visual_critic",
            RunStatus.CRITIC_COMPLETE: "run_draft_qa",
            RunStatus.REVISION_REQUESTED: "revise_artwork",
            RunStatus.ARTWORK_REVISED: "regenerate_after_revision",
            RunStatus.REVISED_CANDIDATES_READY: "render_candidate_previews",
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

    def _plan_design(self, state: PackagingState) -> None:
        self.budget.check(state, "plan_design")
        project = self._project(state)
        prompts = default_prompts()
        planner_input = build_planner_input(project)
        input_hash = planner_input_hash(planner_input, prompts)
        prompt_hash = planner_prompt_hash(prompts)
        system_prompt_hash = next(p.sha256 for p in prompts if p.prompt_id.endswith("system"))
        task_prompt_hash = next(p.sha256 for p in prompts if p.prompt_id.endswith("planner"))
        planner_settings = PlannerSettings()
        provider = (
            OpenAICompatiblePlannerProvider()
            if self.online and planner_settings.provider == "openai-compatible"
            else MockPlannerProvider()
        )
        request = PlannerRequest(
            planner_input=planner_input,
            prompt_id="design_planner",
            prompt_version="v2",
            prompt_hash=prompt_hash,
            system_prompt_hash=system_prompt_hash,
            task_prompt_hash=task_prompt_hash,
            creative_brief_hash=planner_input.creative_brief_hash,
            input_hash=input_hash,
            model_config_payload={"temperature": 0},
        )
        state["planner_request_ref"] = self.store.write_json(
            state["run_id"], "plan/planner_request.json", request.model_dump(mode="json")
        )
        existing = self.store.path(state["run_id"], "plan/design_plan.json")
        provenance_path = self.store.path(state["run_id"], "plan/planner_provenance.json")
        if (
            existing.exists()
            and provenance_path.exists()
            and self._planner_cache_matches(provenance_path, request, provider)
        ):
            plan = DesignPlan.model_validate_json(existing.read_text(encoding="utf-8"))
            state["cache_hits"] += 1
        else:
            try:
                result, attempts = run_with_retry(
                    lambda: provider.create_design_plan(
                        request,
                        ProviderContext(
                            run_id=state["run_id"], thread_id=state["thread_id"], node="plan_design"
                        ),
                    ),
                    RetryPolicy(max_attempts=2, initial_backoff_seconds=0.01),
                )
            except ProviderConfigurationError:
                state["errors"].append(
                    WorkflowError(
                        code="PROVIDER_CONFIGURATION",
                        message="planner provider is not configured",
                        node="plan_design",
                    )
                )
                self._transition(state, RunStatus.PROVIDER_CONFIGURATION_FAILED, "plan_design")
                return
            except ProviderSchemaError as exc:
                if not self.online:
                    state["errors"].append(
                        WorkflowError(code=exc.code, message=str(exc), node="plan_design")
                    )
                    self._transition(state, RunStatus.PLANNING_FAILED, "plan_design")
                    return
                state["errors"].append(
                    WorkflowError(
                        code=exc.code,
                        message=f"{exc}; fell back to mock planner",
                        node="plan_design",
                    )
                )
                provider = MockPlannerProvider()
                result = provider.create_design_plan(
                    request,
                    ProviderContext(
                        run_id=state["run_id"], thread_id=state["thread_id"], node="plan_design"
                    ),
                )
                attempts = 0
            except ProviderError as exc:
                if not self.online:
                    state["errors"].append(
                        WorkflowError(code=exc.code, message=str(exc), node="plan_design")
                    )
                    self._transition(state, RunStatus.PROVIDER_FAILED, "plan_design")
                    return
                state["errors"].append(
                    WorkflowError(
                        code=exc.code,
                        message=f"{exc}; fell back to mock planner",
                        node="plan_design",
                    )
                )
                provider = MockPlannerProvider()
                result = provider.create_design_plan(
                    request,
                    ProviderContext(
                        run_id=state["run_id"], thread_id=state["thread_id"], node="plan_design"
                    ),
                )
                attempts = 0
            state["provider_attempts"] += attempts
            state["llm_calls"] += 1
            plan = result.design_plan
            if validate_immutable_facts(project, plan):
                self._transition(state, RunStatus.PLANNING_FAILED, "plan_design")
                return
            state["planner_provider"] = result.provenance.provider
            state["planner_model"] = result.provenance.model
            state["spent_estimate"] += result.provenance.cost_estimate
            state["token_usage"] = result.provenance.usage.model_dump(mode="json")
            self.store.write_json(
                state["run_id"], "plan/design_plan.json", plan.model_dump(mode="json")
            )
            self.store.write_json(
                state["run_id"],
                "plan/planner_provenance.json",
                result.provenance.model_dump(mode="json"),
            )
        state["design_plan_ref"] = str(existing)
        state["design_plan_hash"] = stable_hash(plan.model_dump(mode="json"))
        self._transition(state, RunStatus.DESIGN_INPUTS_READY, "plan_design")

    def _generate_artworks(self, state: PackagingState) -> None:
        plan_path = Path(
            state["design_plan_ref"] or self.store.path(state["run_id"], "plan/design_plan.json")
        )
        plan = DesignPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
        refs: list[str] = []
        image_settings = ImageSettings()
        try:
            provider = (
                OpenAICompatibleImageProvider()
                if self.online and image_settings.provider == "openai-compatible"
                else FixtureArtworkProvider()
            )
        except ProviderConfigurationError as exc:
            state["errors"].append(
                WorkflowError(code=exc.code, message=str(exc), node="generate_artworks")
            )
            self._transition(
                state, RunStatus.PROVIDER_CONFIGURATION_FAILED, "generate_artworks"
            )
            return
        artwork_count = min(image_settings.default_count, image_settings.hard_max_calls)
        for concept in plan.artwork_concepts[:artwork_count]:
            path = self.store.path(state["run_id"], f"artwork/{concept.concept_id}.png")
            prompt, negative_prompt = build_artwork_prompt(concept.prompt, plan, "square")
            req_hash = stable_cache_key(
                {
                    "concept": concept.model_dump(mode="json"),
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "provider": provider.provider,
                    "model": provider.model,
                    "target_dimensions": [
                        image_settings.target_width_px,
                        image_settings.target_height_px,
                    ],
                    "output_format": image_settings.output_format,
                    "prompt_template_version": "v1",
                }
            )
            request = ArtworkRequest(
                concept_id=concept.concept_id,
                prompt=prompt,
                negative_prompt=negative_prompt,
                target_width_px=image_settings.target_width_px,
                target_height_px=image_settings.target_height_px,
                request_hash=req_hash,
                output_format=image_settings.output_format,
            )
            manifest_path = path.with_suffix(".manifest.json")
            if (
                path.exists()
                and self._artwork_cache_matches(manifest_path, request, provider, path)
            ):
                refs.append(str(path))
                state["cache_hits"] += 1
                state["artwork_hashes"][concept.concept_id] = file_hash(path)
                continue
            shared_path = self._shared_artwork_cache_path(request)
            shared_manifest = shared_path.with_suffix(".manifest.json")
            if (
                shared_path.exists()
                and self._artwork_cache_matches(shared_manifest, request, provider, shared_path)
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(shared_path, path)
                self._write_artwork_manifest(manifest_path, request, provider, file_hash(path))
                refs.append(str(path))
                state["cache_hits"] += 1
                state["artwork_hashes"][concept.concept_id] = file_hash(path)
                continue
            try:
                def generate_call(
                    provider_arg: FixtureArtworkProvider | OpenAICompatibleImageProvider = provider,
                    request_arg: ArtworkRequest = request,
                ) -> ArtworkResult:
                    return provider_arg.generate(
                        request_arg,
                        ProviderContext(
                            run_id=state["run_id"],
                            thread_id=state["thread_id"],
                            node="generate_artworks",
                        ),
                        self.store.path(state["run_id"], "artwork"),
                    )

                result, attempts = run_with_retry(
                    generate_call,
                    RetryPolicy(max_attempts=2, initial_backoff_seconds=0.01),
                )
            except ProviderConfigurationError as exc:
                state["errors"].append(
                    WorkflowError(code=exc.code, message=str(exc), node="generate_artworks")
                )
                self._transition(
                    state, RunStatus.PROVIDER_CONFIGURATION_FAILED, "generate_artworks"
                )
                return
            except ProviderError as exc:
                state["errors"].append(
                    WorkflowError(code=exc.code, message=str(exc), node="generate_artworks")
                )
                self._transition(state, RunStatus.ARTWORK_FAILED, "generate_artworks")
                return
            state["provider_attempts"] += attempts
            state["image_calls"] += 1
            refs.append(result.artifact_ref)
            state["artwork_hashes"][concept.concept_id] = result.sha256
            self._write_artwork_manifest(manifest_path, request, provider, result.sha256)
            shared_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(result.artifact_ref, shared_path)
            self._write_artwork_manifest(shared_manifest, request, provider, result.sha256)
            if result.provenance:
                self.store.write_json_once(
                    state["run_id"],
                    f"artwork/{concept.concept_id}.provenance.json",
                    result.provenance.model_dump(mode="json"),
                )
        state["artwork_refs"] = refs
        state["image_provider"] = provider.provider
        state["image_model"] = provider.model
        self._transition(state, RunStatus.ARTWORK_READY, "generate_artworks")

    def _generate_layout_candidates(self, state: PackagingState) -> None:
        project = self._project(state)
        dieline = load_dieline(project.packaging.size_id)
        plan = DesignPlan.model_validate_json(Path(state["design_plan_ref"] or "").read_text())
        artwork_refs = self._artwork_ref_map(state)
        candidates = [
            c
            for c in attach_artwork_layers(
                generate_candidates(
                    project,
                    dieline,
                    seed=int(sha256(state["run_id"].encode("utf-8")).hexdigest()[:8], 16),
                    design_plan=plan,
                ),
                artwork_refs,
                state["artwork_hashes"],
            )
            if candidate_passed(evaluate_candidate(project, dieline, c))
        ]
        self.budget.check(state, "generate_layout_candidates", len(candidates))
        if not candidates:
            self._transition(state, RunStatus.FAILED_LAYOUT, "generate_layout_candidates")
            return
        ref = self.store.write_json(
            state["run_id"],
            "candidates/candidates.json",
            [c.model_dump(mode="json") for c in candidates],
        )
        state["candidate_refs"] = [ref]
        self._transition(state, RunStatus.CANDIDATES_READY, "generate_layout_candidates")

    def _render_candidate_previews(self, state: PackagingState) -> None:
        project = self._project(state)
        dieline = load_dieline(project.packaging.size_id)
        temp_dir = self.store.run_dir(state["run_id"])
        preview_refs: list[str] = []
        for candidate in self._load_candidates(state):
            preview = self.store.path(state["run_id"], f"previews/{candidate.candidate_id}.png")
            dep_hash = self._render_dependency_hash(state, candidate, dieline.version)
            manifest_path = preview.with_suffix(".manifest.json")
            preview.parent.mkdir(parents=True, exist_ok=True)
            if self._needs_render(manifest_path, dep_hash) or not preview.exists():
                try:
                    render_manifest(
                        LayoutManifest(
                            run_id=state["run_id"],
                            project_id=project.project_id,
                            dieline_version=dieline.version,
                            candidate=candidate,
                            artwork_refs=self._artwork_ref_map(state),
                            artwork_hashes=state["artwork_hashes"],
                            metadata={
                                "dependency_hash": dep_hash,
                                "renderer_version": RENDERER_VERSION,
                            },
                        ),
                        project,
                        dieline,
                        temp_dir,
                    )
                except RenderAssetError:
                    self._transition(state, RunStatus.FAILED_RENDER, "render_candidate_previews")
                    return
                final_png = temp_dir / "final" / "final_preview.png"
                shutil.copyfile(final_png, preview)
                self._write_dependency_manifest(
                    manifest_path, dep_hash, {"png_hash": file_hash(preview)}
                )
            state["preview_hashes"][candidate.candidate_id] = file_hash(preview)
            state["preview_dependency_hashes"][candidate.candidate_id] = dep_hash
            preview_refs.append(str(preview))
        state["preview_refs"] = preview_refs
        self._transition(state, RunStatus.PREVIEWS_READY, "render_candidate_previews")

    def _prepare_contact_sheet(self, state: PackagingState) -> None:
        candidates = self._load_candidates(state)
        if len(candidates) == 1:
            candidate = candidates[0]
            state["selected_candidate_id"] = candidate.candidate_id
            state["selected_candidate_hash"] = stable_hash(candidate.model_dump(mode="json"))
            self._transition(state, RunStatus.DRAFT_QA_PASSED, "prepare_contact_sheet")
            return
        top_k = select_top_k(candidates, WorkflowBudgetSettings().contact_sheet_top_k, 8)
        previews = {Path(path).stem: Path(path) for path in state["preview_refs"]}
        output = self.store.path(state["run_id"], "previews/contact_sheet.png")
        manifest_json = self.store.path(state["run_id"], "previews/contact_sheet.manifest.json")
        dep_hash = stable_hash(
            {
                "candidate_hashes": {
                    c.candidate_id: stable_hash(c.model_dump(mode="json")) for c in top_k
                },
                "preview_hashes": {
                    cid: file_hash(path)
                    for cid, path in previews.items()
                    if cid in {c.candidate_id for c in top_k}
                },
                "renderer_version": CONTACT_SHEET_RENDERER_VERSION,
            }
        )
        if self._needs_render(manifest_json, dep_hash) or not output.exists():
            manifest = render_contact_sheet(previews, top_k, output, manifest_json)
            data = json.loads(manifest_json.read_text(encoding="utf-8"))
            data["dependency_hash"] = dep_hash
            manifest_json.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        else:
            data = json.loads(manifest_json.read_text(encoding="utf-8"))
            manifest = type(
                "ContactSheetState", (), {"contact_sheet_hash": data["contact_sheet_hash"]}
            )()
        state["contact_sheet_ref"] = str(
            self.store.path(state["run_id"], "previews/contact_sheet.png")
        )
        state["contact_sheet_hash"] = manifest.contact_sheet_hash
        state["contact_sheet_dependency_hash"] = dep_hash
        self._transition(state, RunStatus.CONTACT_SHEET_READY, "prepare_contact_sheet")

    def _visual_critic(self, state: PackagingState) -> None:
        if state["vision_calls"] >= self.budget.policy.max_vision_calls:
            state["waiting_for_human_selection"] = True
            self._transition(state, RunStatus.WAITING_HUMAN_SELECTION, "visual_critic")
            return
        manifest_path = self.store.path(state["run_id"], "previews/contact_sheet.manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        plan = DesignPlan.model_validate_json(Path(state["design_plan_ref"] or "").read_text())
        prompts = critic_prompts()
        prompt_hash = sha256("".join(p.sha256 for p in prompts).encode("utf-8")).hexdigest()
        try:
            vision_settings = VisionSettings()
            provider = (
                OpenAICompatibleVisionCriticProvider()
                if self.online and vision_settings.provider == "openai-compatible"
                else MockVisualCriticProvider()
            )
        except ProviderConfigurationError:
            state["errors"].append(
                WorkflowError(
                    code="PROVIDER_CONFIGURATION",
                    message="vision provider is not configured",
                    node="visual_critic",
                )
            )
            self._transition(state, RunStatus.PROVIDER_CONFIGURATION_FAILED, "visual_critic")
            return
        request_hash = critic_cache_key(
            {
                "contact_sheet_hash": manifest["contact_sheet_hash"],
                "candidate_hashes": manifest["candidate_hashes"],
                "prompt_hash": prompt_hash,
                "schema_version": "v1",
                "rubric_version": RUBRIC_VERSION,
                "provider": provider.provider,
                "model": provider.model,
            }
        )
        request = CriticRequest(
            contact_sheet_path=Path(state["contact_sheet_ref"] or ""),
            contact_sheet_hash=manifest["contact_sheet_hash"],
            candidate_ids=list(manifest["candidate_order"]),
            candidate_hashes=dict(manifest["candidate_hashes"]),
            artwork_ids=list(state["artwork_hashes"].keys()),
            brand_summary=self._project(state).producer.manufacturer_name,
            visual_direction=plan.visual_direction,
            product_category=self._project(state).product.category,
            layout_intent_summary=(
                f"{plan.layout_intents[0].panel_strategy}; "
                f"palette={', '.join(plan.palette)}; "
                f"motifs={', '.join(plan.decorative_motifs)}"
            ),
            hard_constraint_summary=(
                "all candidates on contact sheet passed deterministic hard constraints"
            ),
            prompt_id="visual_critic",
            prompt_version="v1",
            prompt_hash=prompt_hash,
            schema_version="v1",
            rubric_version=RUBRIC_VERSION,
            request_hash=request_hash,
        )
        state["critic_request_ref"] = self.store.write_json_once(
            state["run_id"], "critic/critic_request.json", request.model_dump(mode="json")
        )
        self._transition(state, RunStatus.CRITIC_RUNNING, "visual_critic")
        try:
            result = provider.evaluate(
                request,
                ProviderContext(
                    run_id=state["run_id"], thread_id=state["thread_id"], node="visual_critic"
                ),
            )
        except ProviderSchemaError as exc:
            state["vision_calls"] += 1
            state["errors"].append(
                WorkflowError(code=exc.code, message=str(exc), node="visual_critic")
            )
            self._transition(state, RunStatus.CRITIC_FAILED, "visual_critic")
            return
        except ProviderError as exc:
            state["errors"].append(
                WorkflowError(code=exc.code, message=str(exc), node="visual_critic")
            )
            self._transition(state, RunStatus.PROVIDER_FAILED, "visual_critic")
            return
        try:
            validate_critic_decision(
                result.decision,
                CriticGuardContext(set(request.candidate_ids), set(request.artwork_ids)),
            )
        except ValueError as exc:
            code = getattr(exc, "code", "CRITIC_GUARD_REJECTED")
            state["vision_calls"] += 1
            state["errors"].append(WorkflowError(code=code, message=str(exc), node="visual_critic"))
            self._transition(state, RunStatus.CRITIC_FAILED, "visual_critic")
            return
        state["vision_calls"] += 1
        state["vision_provider"] = result.provider
        state["vision_model"] = result.model_id
        selected = result.decision.selected_candidate_id
        state["critic_decision_ref"] = self.store.write_json(
            state["run_id"], "critic/critic_decision.json", result.decision.model_dump(mode="json")
        )
        if result.provenance:
            self.store.write_json(
                state["run_id"],
                "critic/critic_provenance.json",
                result.provenance.model_dump(mode="json"),
            )
            state["critic_decision_hash"] = result.provenance.decision_hash
        if result.decision.status == "PASS" and selected is not None:
            candidate = next(c for c in self._load_candidates(state) if c.candidate_id == selected)
            state["selected_candidate_id"] = selected
            state["selected_candidate_hash"] = stable_hash(candidate.model_dump(mode="json"))
        elif result.decision.status == "REVISE_ARTWORK" and result.decision.targeted_revision:
            if state["revision_count"] >= self.budget.policy.max_revisions:
                self._transition(state, RunStatus.REVISION_BUDGET_EXCEEDED, "visual_critic")
                return
            self._transition(state, RunStatus.REVISION_REQUESTED, "visual_critic")
            return
        else:
            state["waiting_for_human_selection"] = True
            self._transition(state, RunStatus.WAITING_HUMAN_SELECTION, "visual_critic")
            return
        self._transition(state, RunStatus.CRITIC_COMPLETE, "visual_critic")

    def _revise_artwork(self, state: PackagingState) -> None:
        decision_path = Path(state["critic_decision_ref"] or "")
        from ocop_pack.agents.visual_critic.schemas import CriticDecision

        decision = CriticDecision.model_validate_json(decision_path.read_text(encoding="utf-8"))
        target = decision.targeted_revision
        if target is None:
            self._transition(state, RunStatus.WAITING_HUMAN_SELECTION, "revise_artwork")
            return
        if state["image_edit_calls"] >= self.budget.policy.max_image_edit_calls:
            self._transition(state, RunStatus.REVISION_BUDGET_EXCEEDED, "revise_artwork")
            return
        source_path = Path(self._artwork_ref_map(state)[target.artwork_id])
        plan = DesignPlan.model_validate_json(Path(state["design_plan_ref"] or "").read_text())
        settings = RevisionSettings()
        provider = FixtureArtworkRevisionProvider()
        request = ArtworkRevisionRequest(
            source_artwork_path=source_path,
            source_artwork_id=target.artwork_id,
            source_artwork_hash=state["artwork_hashes"][target.artwork_id],
            targeted_revision=target,
            visual_direction=plan.visual_direction,
            target_width_px=ImageSettings().target_width_px,
            target_height_px=ImageSettings().target_height_px,
            request_hash=revision_cache_key(
                {
                    "source_hash": state["artwork_hashes"][target.artwork_id],
                    "targeted_revision": target.model_dump(mode="json"),
                    "provider": settings.provider,
                    "model": settings.model,
                }
            ),
        )
        result = provider.revise(
            request,
            ProviderContext(
                run_id=state["run_id"], thread_id=state["thread_id"], node="revise_artwork"
            ),
            self.store.path(state["run_id"], "artwork"),
        )
        state["revision_count"] += 1
        state["image_edit_calls"] += 1
        state["revised_artwork_ref"] = result.artifact_ref
        state["revised_artwork_hash"] = result.sha256
        state["revision_provider"] = result.provider
        state["revision_model"] = result.model
        state["artwork_hashes"][target.artwork_id] = result.sha256
        state["artwork_refs"] = [
            result.artifact_ref if Path(ref).stem.split(".", 1)[0] == target.artwork_id else ref
            for ref in state["artwork_refs"]
        ]
        state["revision_request_ref"] = self.store.write_json(
            state["run_id"], "critic/revision_request.json", request.model_dump(mode="json")
        )
        if result.provenance:
            self.store.write_json(
                state["run_id"],
                "artwork/revision_provenance.json",
                result.provenance.model_dump(mode="json"),
            )
        self._transition(state, RunStatus.ARTWORK_REVISED, "revise_artwork")

    def _regenerate_after_revision(self, state: PackagingState) -> None:
        state["selected_candidate_id"] = None
        state["selected_candidate_hash"] = None
        state["approval"] = None
        state["contact_sheet_ref"] = None
        state["contact_sheet_hash"] = None
        state["final_png_ref"] = None
        state["final_pdf_ref"] = None
        current = state["status"]
        state["status"] = RunStatus.ARTWORK_READY
        self._generate_layout_candidates(state)
        state["status"] = current
        state["status"] = RunStatus.REVISED_CANDIDATES_READY

    def _run_draft_qa(self, state: PackagingState) -> None:
        preview = next(
            (
                Path(path)
                for path in state["preview_refs"]
                if Path(path).stem == state["selected_candidate_id"]
            ),
            Path(state["preview_refs"][-1]),
        )
        report = self._qa(state, preview)
        state["qa_report_ref"] = self.store.write_json_once(
            state["run_id"], "qa/draft_qa_report.json", report.model_dump(mode="json")
        )
        if not report.passed:
            self._record_qa_failure(state, report, "run_draft_qa", "qa/draft_failures.json")
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
        final_png = self.store.path(state["run_id"], "final/packaging.png")
        final_pdf = self.store.path(state["run_id"], "final/packaging.pdf")
        final_svg = self.store.path(state["run_id"], "final/packaging.svg")
        dep_hash = self._render_dependency_hash(state, candidate, dieline.version)
        manifest_path = self.store.path(state["run_id"], "final/packaging.manifest.json")
        if (
            self._needs_render(manifest_path, dep_hash)
            or not final_png.exists()
            or not final_pdf.exists()
            or not final_svg.exists()
        ):
            layout_manifest = LayoutManifest(
                run_id=state["run_id"],
                project_id=project.project_id,
                dieline_version=dieline.version,
                candidate=candidate,
                artwork_refs=self._artwork_ref_map(state),
                artwork_hashes=state["artwork_hashes"],
                metadata={
                    "dependency_hash": dep_hash,
                    "renderer_version": RENDERER_VERSION,
                },
            )
            try:
                png, pdf, _ = render_manifest(
                    layout_manifest,
                    project,
                    dieline,
                    self.store.run_dir(state["run_id"]),
                )
                svg = render_svg_manifest(layout_manifest, project, dieline, final_svg)
            except RenderAssetError:
                self._transition(state, RunStatus.FAILED_RENDER, "render_final_outputs")
                return
            shutil.copyfile(png, final_png)
            shutil.copyfile(pdf, final_pdf)
            self._write_dependency_manifest(
                manifest_path,
                dep_hash,
                {
                    "png_hash": file_hash(final_png),
                    "pdf_hash": file_hash(final_pdf),
                    "svg_hash": file_hash(svg),
                },
            )
        state["final_png_ref"] = str(final_png)
        state["final_pdf_ref"] = str(final_pdf)
        state["final_render_hash"] = dep_hash
        state["artifact_refs"]["final:svg"] = str(final_svg)
        editable_ref = self.store.write_json(
            state["run_id"],
            "final/editable_layout.json",
            {
                "schema_version": "editable-layout.v1",
                "run_id": state["run_id"],
                "project_id": project.project_id,
                "units": "mm",
                "canvas": {
                    "width_mm": dieline.width_mm,
                    "height_mm": dieline.height_mm,
                    "dieline_version": dieline.version,
                },
                "candidate": candidate.model_dump(mode="json"),
                "artwork_refs": self._artwork_ref_map(state),
                "artwork_hashes": state["artwork_hashes"],
                "assets": {
                    "ocop_logo": str(project.branding.ocop.logo_path),
                    "brand_logos": [
                        logo.model_dump(mode="json") for logo in project.branding.logos
                    ],
                },
                "preview": str(final_png),
                "print_pdf": str(final_pdf),
            },
        )
        print_spec_ref = self.store.write_json(
            state["run_id"],
            "final/print_spec.json",
            {
                "recommended_file": str(final_pdf),
                "fallback_png": str(final_png),
                "canvas_width_mm": dieline.width_mm,
                "canvas_height_mm": dieline.height_mm,
                "png_dpi": PNG_RENDER_DPI,
                "png_width_px": round(dieline.width_mm / 25.4 * PNG_RENDER_DPI),
                "png_height_px": round(dieline.height_mm / 25.4 * PNG_RENDER_DPI),
                "print_scale": "100%",
                "notes": [
                    "Use the PDF for printing; text, QR, and vector shapes stay sharper.",
                    "Use the PNG only when the print vendor cannot accept PDF.",
                    "Do not upscale or fit-to-page; print at 100% scale.",
                ],
                "renderer_version": RENDERER_VERSION,
            },
        )
        state["artifact_refs"]["final:editable_layout"] = editable_ref
        state["artifact_refs"]["final:print_spec"] = print_spec_ref
        self._transition(state, RunStatus.FINAL_RENDERED, "render_final_outputs")

    def _run_final_qa(self, state: PackagingState) -> None:
        report = self._qa(state, Path(state["final_png_ref"] or ""))
        state["qa_report_ref"] = self.store.write_json_once(
            state["run_id"], "qa/qa_report.json", report.model_dump(mode="json")
        )
        if not report.passed:
            self._record_qa_failure(state, report, "run_final_qa", "qa/final_failures.json")
        self._transition(
            state,
            RunStatus.FINAL_QA_PASSED if report.passed else RunStatus.FAILED_QA,
            "run_final_qa",
        )

    def _export_bundle(self, state: PackagingState) -> None:
        self._validate_approval(state)
        manifest = {
            "state": self._serializable(state),
            "final": {
                "png": state["final_png_ref"],
                "pdf": state["final_pdf_ref"],
                "svg": state["artifact_refs"].get("final:svg"),
            },
            "editable": {"layout": state["artifact_refs"].get("final:editable_layout")},
            "print": {"spec": state["artifact_refs"].get("final:print_spec")},
        }
        self.store.write_json(state["run_id"], "run_manifest.json", manifest)
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

    def _record_qa_failure(
        self, state: PackagingState, report: QAReport, node: str, relative: str
    ) -> None:
        failed = [item for item in report.results if not item.passed]
        rule_ids = ", ".join(item.rule_id for item in failed[:8]) or "unknown"
        ref = self.store.write_json(
            state["run_id"],
            relative,
            {
                "run_id": state["run_id"],
                "candidate_id": report.candidate_id,
                "status": "FAILED_QA",
                "failed_count": len(failed),
                "critical_count": sum(item.severity == "critical" for item in failed),
                "rules": [
                    {
                        "rule_id": item.rule_id,
                        "severity": item.severity,
                        "element_ids": item.element_ids,
                        "message": item.message,
                        "action_hint": self._qa_action_hint(item.rule_id),
                        "details": item.details,
                    }
                    for item in failed
                ],
            },
        )
        state["artifact_refs"][f"qa:{node}:failures"] = ref
        state["errors"].append(
            WorkflowError(
                code="QA_FAILED",
                message=(
                    f"{len(failed)} QA rule(s) failed for {report.candidate_id}: "
                    f"{rule_ids}; details={ref}"
                ),
                node=node,
            )
        )

    def _qa_action_hint(self, rule_id: str) -> str:
        if rule_id.startswith("TYPO"):
            return "Increase text box size, reduce text length, or use a larger readable layout."
        if rule_id in {"HC-04", "HC-05", "HC-06"}:
            return "Check logo count, logo aspect ratio, and logo placement."
        if rule_id.startswith("HC-1"):
            return "Move the affected element inside its panel and away from protected zones."
        if rule_id.startswith("QR"):
            return "Increase QR size or restore the QR quiet zone."
        return "Open the QA report for rule details."

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

    def _artwork_ref_map(self, state: PackagingState) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for ref in state["artwork_refs"]:
            path = Path(ref)
            mapping[path.stem.split(".", 1)[0]] = str(path)
        return mapping

    def _render_dependency_hash(
        self, state: PackagingState, candidate: LayoutCandidate, dieline_version: str
    ) -> str:
        artwork_id = str(candidate.metadata.get("artwork_id", ""))
        return stable_hash(
            {
                "candidate": candidate.model_dump(mode="json"),
                "artwork_ref": self._artwork_ref_map(state).get(artwork_id),
                "artwork_hash": state["artwork_hashes"].get(artwork_id),
                "dieline_version": dieline_version,
                "project_hash": state["project_hash"],
                "renderer_version": RENDERER_VERSION,
            }
        )

    def _needs_render(self, manifest_path: Path, dependency_hash: str) -> bool:
        if not manifest_path.exists():
            return True
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return True
        return str(data.get("dependency_hash")) != dependency_hash

    def _planner_cache_matches(
        self,
        provenance_path: Path,
        request: PlannerRequest,
        provider: MockPlannerProvider | OpenAICompatiblePlannerProvider,
    ) -> bool:
        try:
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        expected = {
            "input_hash": request.input_hash,
            "creative_brief_hash": request.creative_brief_hash,
            "prompt_hash": request.prompt_hash,
            "system_prompt_hash": request.system_prompt_hash,
            "task_prompt_hash": request.task_prompt_hash,
            "schema_version": "design-plan.v2",
            "provider": provider.provider,
            "model": provider.model,
            "planner_policy_version": request.planner_policy_version,
        }
        return all(provenance.get(key) == value for key, value in expected.items())

    def _shared_artwork_cache_path(self, request: ArtworkRequest) -> Path:
        return self.store.runs_root / "_cache" / "artwork" / f"{request.request_hash}.png"

    def _write_artwork_manifest(
        self,
        manifest_path: Path,
        request: ArtworkRequest,
        provider: FixtureArtworkProvider | OpenAICompatibleImageProvider,
        artifact_sha256: str,
    ) -> None:
        self._write_dependency_manifest(
            manifest_path,
            request.request_hash,
            {
                "artifact_sha256": artifact_sha256,
                "concept_id": request.concept_id,
                "provider": provider.provider,
                "model": provider.model,
                "width": str(request.target_width_px),
                "height": str(request.target_height_px),
                "output_format": request.output_format,
            },
        )

    def _artwork_cache_matches(
        self,
        manifest_path: Path,
        request: ArtworkRequest,
        provider: FixtureArtworkProvider | OpenAICompatibleImageProvider,
        artifact_path: Path,
    ) -> bool:
        if not manifest_path.exists():
            return False
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        if data.get("artifact_sha256") != file_hash(artifact_path):
            return False
        return all(
            data.get(key) == value
            for key, value in {
                "dependency_hash": request.request_hash,
                "concept_id": request.concept_id,
                "provider": provider.provider,
                "model": provider.model,
                "width": str(request.target_width_px),
                "height": str(request.target_height_px),
                "output_format": request.output_format,
            }.items()
        )

    def _write_dependency_manifest(
        self, manifest_path: Path, dependency_hash: str, payload: dict[str, str]
    ) -> None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps({"dependency_hash": dependency_hash, **payload}, indent=2, sort_keys=True),
            encoding="utf-8",
        )

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
            key: self._serializable_value(value) for key, value in state.items() if key != "project"
        }

    def _serializable_value(self, value: object) -> object:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, list):
            return [self._serializable_value(item) for item in value]
        if isinstance(value, dict):
            return {key: self._serializable_value(item) for key, item in value.items()}
        return value


def artifact_hash(path: str | None) -> str | None:
    return file_hash(Path(path)) if path else None
