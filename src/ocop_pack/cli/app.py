from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, cast

import typer
from sqlalchemy.orm import Session

from ocop_pack.domain.artifacts import ArtifactMetadata
from ocop_pack.domain.dieline import load_dieline
from ocop_pack.domain.layout import LayoutManifest
from ocop_pack.domain.runs import RunRecord, RunStatus
from ocop_pack.engine.candidate_generator import generate_candidates
from ocop_pack.infrastructure.config import (
    DEFAULT_DB_URL,
    ImageSettings,
    PlannerSettings,
    RevisionSettings,
    VisionSettings,
)
from ocop_pack.infrastructure.persistence.repositories import (
    SqlArtifactRepository,
    SqlCandidateRepository,
    SqlRunRepository,
)
from ocop_pack.infrastructure.persistence.session import (
    init_db as create_schema,
)
from ocop_pack.infrastructure.persistence.session import (
    make_engine,
    session_factory,
)
from ocop_pack.orchestration.errors import WorkflowException
from ocop_pack.orchestration.runner import WorkflowRunner
from ocop_pack.orchestration.status import RunStatus as WorkflowRunStatus
from ocop_pack.services.qa_service import qa_candidate
from ocop_pack.services.render_service import render_manifest
from ocop_pack.services.validation_service import file_sha256, load_project, project_hash

app = typer.Typer()
providers_app = typer.Typer(help="Provider capability checks")
app.add_typer(providers_app, name="providers")


def _runner() -> WorkflowRunner:
    return WorkflowRunner()


def _workflow_runner(online: bool | None = None) -> WorkflowRunner:
    return WorkflowRunner(online=online)


def _handle_workflow_error(exc: WorkflowException, verbose: bool = False) -> None:
    if verbose:
        raise exc
    typer.echo(f"Error [{exc.error.code}]: {exc.error.message}", err=True)
    raise typer.Exit(2) from exc


@providers_app.command("check")
def providers_check(
    planner: bool = typer.Option(False, "--planner"),
    image: bool = typer.Option(False, "--image"),
    vision: bool = typer.Option(False, "--vision"),
    revision: bool = typer.Option(False, "--revision"),
) -> None:
    """Validate provider config without printing secrets.

    Offline providers are treated as capability-pass for CI. Sandbox real network
    probes are intentionally performed by the provider adapters during `run`.
    """
    check_all = not planner and not image and not vision and not revision
    try:
        if check_all or planner:
            planner_settings = PlannerSettings()
            typer.echo(
                f"planner provider={planner_settings.provider} model={planner_settings.model}"
            )
            if planner_settings.provider != "mock" and not (
                planner_settings.base_url and planner_settings.api_key
            ):
                typer.echo("planner config invalid: base_url/api_key required", err=True)
                raise typer.Exit(10)
        if check_all or image:
            image_settings = ImageSettings()
            typer.echo(f"image provider={image_settings.provider} model={image_settings.model}")
            if image_settings.provider != "fixture" and not (
                image_settings.base_url and image_settings.api_key
            ):
                typer.echo("image config invalid: base_url/api_key required", err=True)
                raise typer.Exit(10)
        if check_all or vision:
            vision_settings = VisionSettings()
            typer.echo(f"vision provider={vision_settings.provider} model={vision_settings.model}")
            if vision_settings.provider != "mock" and not (
                vision_settings.base_url and vision_settings.api_key
            ):
                typer.echo("vision config invalid: base_url/api_key required", err=True)
                raise typer.Exit(10)
        if check_all or revision:
            revision_settings = RevisionSettings()
            typer.echo(
                f"revision provider={revision_settings.provider} model={revision_settings.model}"
            )
            if revision_settings.provider != "fixture" and not (
                revision_settings.base_url and revision_settings.api_key
            ):
                typer.echo("revision config invalid: base_url/api_key required", err=True)
                raise typer.Exit(10)
    except ValueError as exc:
        typer.echo(f"provider config invalid: {exc}", err=True)
        raise typer.Exit(10) from exc
    typer.echo("provider configuration check passed")


def _session() -> Session:
    engine = make_engine(DEFAULT_DB_URL)
    create_schema(engine)
    return session_factory(engine)()


@app.command()
def validate(project_yaml: Path) -> None:
    load_project(project_yaml)
    typer.echo("valid")


@app.command("init-db")
def init_db_cmd() -> None:
    create_schema(make_engine(DEFAULT_DB_URL))
    typer.echo("database initialized")


@app.command("generate-candidates")
def generate_candidates_cmd(project_yaml: Path, run_id: str = typer.Option(...)) -> None:
    project = load_project(project_yaml)
    dieline = load_dieline(project.packaging.size_id)
    candidates = generate_candidates(project, dieline)
    with _session() as s:
        SqlRunRepository(s).create(
            RunRecord(
                run_id=run_id,
                project_id=project.project_id,
                input_hash=project_hash(project),
                dieline_version=dieline.version,
            )
        )
        SqlCandidateRepository(s).save_many(run_id, candidates)
        SqlRunRepository(s).update_status(run_id, RunStatus.CANDIDATES_GENERATED)
    out = Path("runs") / run_id / "candidates"
    out.mkdir(parents=True, exist_ok=True)
    (out / "candidates.json").write_text(
        json.dumps([c.model_dump(mode="json") for c in candidates], indent=2), encoding="utf-8"
    )
    typer.echo(f"generated {len(candidates)} candidates")


@app.command("run")
def run_workflow(
    project_yaml: Path,
    run_id: str = typer.Option(...),
    online: bool = typer.Option(False, "--online/--offline"),
    crash_after: str | None = typer.Option(None),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    try:
        state = _workflow_runner(online).start(project_yaml, run_id, crash_after=crash_after)
    except WorkflowException as exc:
        _handle_workflow_error(exc, verbose)
    typer.echo(f"Run: {state['run_id']}")
    typer.echo(f"Status: {state['status']}")
    if state["preview_refs"]:
        typer.echo(f"Preview: {state['preview_refs'][0]}")
    if state["status"] == WorkflowRunStatus.WAITING_APPROVAL:
        typer.echo("Next:")
        typer.echo(
            f"  ocop-pack approve --run-id {run_id} --candidate {state['selected_candidate_id']}"
        )
        typer.echo("or:")
        typer.echo(f'  ocop-pack reject --run-id {run_id} --reason "..."')


@app.command("render-candidate")
def render_candidate_cmd(
    run_id: str = typer.Option(...),
    candidate_id: str = typer.Option(...),
    project_yaml: Path = Path("examples/projects/tea_basic/project.yaml"),
) -> None:
    project = load_project(project_yaml)
    dieline = load_dieline(project.packaging.size_id)
    with _session() as s:
        candidates = SqlCandidateRepository(s).list_by_run(run_id)
    cand = next(c for c in candidates if c.candidate_id == candidate_id)
    manifest = LayoutManifest(
        run_id=run_id,
        project_id=project.project_id,
        dieline_version=dieline.version,
        candidate=cand,
    )
    out_dir = Path("runs") / run_id
    png, pdf, overlay = render_manifest(manifest, project, dieline, out_dir)
    with _session() as s:
        repo = SqlArtifactRepository(s)
        for kind, path in [("png", png), ("pdf", pdf), ("overlay", overlay)]:
            repo.save(
                ArtifactMetadata(
                    artifact_id=f"{run_id}-{candidate_id}-{kind}",
                    run_id=run_id,
                    candidate_id=candidate_id,
                    kind=cast(Literal["png", "pdf", "overlay", "qa", "manifest"], kind),
                    relative_path=str(path),
                    sha256=file_sha256(path),
                )
            )
        SqlRunRepository(s).update_status(run_id, RunStatus.RENDERED)
    typer.echo(str(png))
    typer.echo(str(pdf))


@app.command("qa")
def qa_cmd(
    run_id: str = typer.Option(...),
    candidate_id: str | None = typer.Option(None),
    project_yaml: Path = Path("examples/projects/tea_basic/project.yaml"),
) -> None:
    if candidate_id is None:
        state = _runner().load_state(run_id)
        typer.echo(f"Status: {state['status']}")
        typer.echo(f"QA: {state['qa_report_ref']}")
        raise typer.Exit(
            0
            if state["status"]
            in {
                WorkflowRunStatus.FINAL_QA_PASSED,
                WorkflowRunStatus.EXPORTED,
                WorkflowRunStatus.WAITING_APPROVAL,
            }
            else 5
        )
    project = load_project(project_yaml)
    dieline = load_dieline(project.packaging.size_id)
    with _session() as s:
        cand = next(
            c
            for c in SqlCandidateRepository(s).list_by_run(run_id)
            if c.candidate_id == candidate_id
        )
    report = qa_candidate(
        run_id, project, dieline, cand, Path("runs") / run_id / "final" / "final_preview.png"
    )
    out = Path("runs") / run_id / "qa" / "qa_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    raise typer.Exit(0 if report.passed else 5)


@app.command("candidates")
def candidates_cmd(
    run_id: str = typer.Option(...), verbose: bool = typer.Option(False, "--verbose")
) -> None:
    try:
        state = _runner().load_state(run_id)
    except WorkflowException as exc:
        _handle_workflow_error(exc, verbose)
    path = (
        Path(state["candidate_refs"][0])
        if state["candidate_refs"]
        else Path("runs") / run_id / "candidates" / "candidates.json"
    )
    typer.echo(str(path))
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        for candidate in data:
            marker = "*" if candidate["candidate_id"] == state["selected_candidate_id"] else " "
            typer.echo(f"{marker} {candidate['candidate_id']} template={candidate['template_id']}")


@app.command("approve")
def approve_cmd(
    run_id: str = typer.Option(...),
    candidate: str = typer.Option(...),
    approved_by: str = typer.Option("cli"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    try:
        state = _runner().approve(run_id, candidate, approved_by=approved_by)
    except WorkflowException as exc:
        _handle_workflow_error(exc, verbose)
    typer.echo(f"Run: {run_id}")
    typer.echo(f"Status: {state['status']}")
    typer.echo(f"PNG: {state['final_png_ref']}")
    typer.echo(f"PDF: {state['final_pdf_ref']}")


@app.command("reject")
def reject_cmd(
    run_id: str = typer.Option(...),
    reason: str = typer.Option(...),
    approved_by: str = typer.Option("cli"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    try:
        state = _runner().reject(run_id, reason, approved_by=approved_by)
    except WorkflowException as exc:
        _handle_workflow_error(exc, verbose)
    typer.echo(f"Run: {run_id}")
    typer.echo(f"Status: {state['status']}")


@app.command("resume")
def resume_cmd(
    run_id: str = typer.Option(...),
    online: bool = typer.Option(False, "--online/--offline"),
    crash_after: str | None = typer.Option(None),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    try:
        state = _workflow_runner(online).resume(run_id, crash_after=crash_after)
    except WorkflowException as exc:
        _handle_workflow_error(exc, verbose)
    typer.echo(f"Run: {run_id}")
    typer.echo(f"Status: {state['status']}")


@app.command("export")
def export_cmd(
    run_id: str = typer.Option(...), verbose: bool = typer.Option(False, "--verbose")
) -> None:
    try:
        state = _runner().resume(run_id)
    except WorkflowException as exc:
        _handle_workflow_error(exc, verbose)
    if state["status"] != WorkflowRunStatus.EXPORTED:
        typer.echo(f"Run is not exported: {state['status']}", err=True)
        raise typer.Exit(5)
    typer.echo(f"PNG: {state['final_png_ref']}")
    typer.echo(f"PDF: {state['final_pdf_ref']}")


@app.command()
def inspect(run_id: str, json_output: bool = typer.Option(False, "--json")) -> None:
    try:
        state = _runner().load_state(run_id)
        if json_output:
            serializable = {
                k: (
                    v.model_dump(mode="json")
                    if hasattr(v, "model_dump")
                    else str(v)
                    if k == "status"
                    else v
                )
                for k, v in state.items()
                if k != "project"
            }
            typer.echo(json.dumps(serializable, indent=2, default=str))
            return
        typer.echo(f"Run: {run_id}")
        typer.echo(f"Status: {state['status']}")
        typer.echo(f"Planner: {state['planner_provider']}/{state['planner_model']}")
        typer.echo(f"Image: {state['image_provider']}/{state['image_model']}")
        typer.echo(f"Vision: {state['vision_provider']}/{state['vision_model']}")
        typer.echo(
            f"Calls: llm={state['llm_calls']} image={state['image_calls']} "
            f"vision={state['vision_calls']} revision={state['revision_count']} "
            f"cache_hits={state['cache_hits']}"
        )
        candidates_path = Path(state["candidate_refs"][0]) if state["candidate_refs"] else None
        if candidates_path and candidates_path.exists():
            typer.echo(f"Valid candidates: {len(json.loads(candidates_path.read_text()))}")
        typer.echo(f"Contact sheet: {state['contact_sheet_ref']}")
        typer.echo(f"Critic decision: {state['critic_decision_ref']}")
        typer.echo(f"Selected candidate: {state['selected_candidate_id']}")
        typer.echo(f"Revision artifact: {state['revised_artwork_ref']}")
        typer.echo(
            "Next required action: "
            + (
                "human approval"
                if state["status"] == WorkflowRunStatus.WAITING_APPROVAL
                else "inspect status"
            )
        )
        typer.echo(f"Design plan: {state['design_plan_ref']}")
        typer.echo(f"Artwork: {state['artwork_refs']}")
        typer.echo(f"Preview: {state['preview_refs'][0] if state['preview_refs'] else None}")
        typer.echo(f"Final PNG: {state['final_png_ref']}")
        typer.echo(f"Final PDF: {state['final_pdf_ref']}")
        return
    except WorkflowException:
        pass
    with _session() as s:
        typer.echo(SqlRunRepository(s).get(run_id))
        typer.echo([a.model_dump() for a in SqlArtifactRepository(s).list_by_run(run_id)])


@app.command("provenance")
def provenance_cmd(run_id: str) -> None:
    root = Path("runs") / run_id
    for path in (
        sorted((root / "plan").glob("*provenance.json"))
        + sorted((root / "artwork").glob("*.provenance.json"))
        + sorted((root / "critic").glob("*provenance.json"))
        + sorted((root / "revision").glob("*provenance.json"))
    ):
        typer.echo(str(path))
        typer.echo(path.read_text(encoding="utf-8"))


@app.command("critic-show")
def critic_show_cmd(run_id: str = typer.Option(...)) -> None:
    root = Path("runs") / run_id / "critic"
    for name in ["critic_request.json", "critic_decision.json", "critic_provenance.json"]:
        path = root / name
        if path.exists():
            typer.echo(str(path))
            typer.echo(path.read_text(encoding="utf-8"))


@app.command("revision-show")
def revision_show_cmd(run_id: str = typer.Option(...)) -> None:
    root = Path("runs") / run_id / "revision"
    for path in sorted(root.glob("*")):
        typer.echo(str(path))


@app.command("select")
def select_cmd(
    run_id: str = typer.Option(...),
    candidate: str = typer.Option(...),
    approved_by: str = typer.Option("cli"),
) -> None:
    state = _runner().approve(run_id, candidate, approved_by=approved_by)
    typer.echo(f"Run: {run_id}")
    typer.echo(f"Status: {state['status']}")
