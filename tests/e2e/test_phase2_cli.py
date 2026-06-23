from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from ocop_pack.cli.app import app

PROJECT = Path("examples/projects/tea_basic/project.yaml")


def _invoke(cli: CliRunner, args: list[str]) -> Any:
    return cli.invoke(
        app,
        args,
        catch_exceptions=True,
        env={"PYTHONIOENCODING": "utf-8"},
        prog_name="ocop-pack",
    )


def _clean_run(run_id: str) -> Path:
    run_dir = Path("runs") / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)
    return run_dir


def test_phase2_cli_happy_path_export() -> None:
    cli = CliRunner()
    run_dir = _clean_run("e2e_happy")

    run_result = _invoke(cli, ["run", str(PROJECT), "--run-id", "e2e_happy"])
    assert run_result.exit_code == 0
    assert "Status: WAITING_APPROVAL" in run_result.output
    assert "approve --run-id e2e_happy" in run_result.output

    inspect_result = _invoke(cli, ["inspect", "e2e_happy"])
    assert inspect_result.exit_code == 0
    assert "Status: WAITING_APPROVAL" in inspect_result.output

    candidates_result = _invoke(cli, ["candidates", "--run-id", "e2e_happy"])
    assert candidates_result.exit_code == 0
    assert "C001" in candidates_result.output

    approve_result = _invoke(cli, ["approve", "--run-id", "e2e_happy", "--candidate", "C001"])
    assert approve_result.exit_code == 0
    assert "Status: EXPORTED" in approve_result.output

    export_result = _invoke(cli, ["export", "--run-id", "e2e_happy"])
    assert export_result.exit_code == 0
    assert "packaging.png" in export_result.output
    assert (run_dir / "final" / "packaging.png").exists()
    assert (run_dir / "final" / "packaging.pdf").exists()

    approval = json.loads((run_dir / "approval" / "approval.json").read_text(encoding="utf-8"))
    assert approval["candidate_id"] == "C001"
    assert approval["candidate_hash"]
    assert approval["project_hash"]


def test_phase2_cli_reject_stops_before_final() -> None:
    cli = CliRunner()
    run_dir = _clean_run("e2e_reject")

    run_result = _invoke(cli, ["run", str(PROJECT), "--run-id", "e2e_reject"])
    assert run_result.exit_code == 0

    reject_result = _invoke(
        cli,
        ["reject", "--run-id", "e2e_reject", "--reason", "Hierarchy is not acceptable"],
    )
    assert reject_result.exit_code == 0
    assert "Status: REJECTED" in reject_result.output
    assert not (run_dir / "final" / "packaging.png").exists()


def test_phase2_cli_invalid_candidate_returns_business_error() -> None:
    cli = CliRunner()
    _clean_run("e2e_invalid")

    run_result = _invoke(cli, ["run", str(PROJECT), "--run-id", "e2e_invalid"])
    assert run_result.exit_code == 0

    approve_result = _invoke(cli, ["approve", "--run-id", "e2e_invalid", "--candidate", "C999"])
    assert approve_result.exit_code == 2
    assert "INVALID_CANDIDATE" in approve_result.output


def test_phase2_cli_crash_resume_no_duplicate_export() -> None:
    cli = CliRunner()
    run_dir = _clean_run("e2e_crash")

    crash_result = _invoke(
        cli,
        [
            "run",
            str(PROJECT),
            "--run-id",
            "e2e_crash",
            "--crash-after",
            "render_candidate_previews",
        ],
    )
    assert crash_result.exit_code != 0

    resume_result = _invoke(cli, ["resume", "--run-id", "e2e_crash"])
    assert resume_result.exit_code == 0
    assert "Status: WAITING_APPROVAL" in resume_result.output

    approve_result = _invoke(cli, ["approve", "--run-id", "e2e_crash", "--candidate", "C001"])
    assert approve_result.exit_code == 0
    assert "Status: EXPORTED" in approve_result.output

    first_manifest = (run_dir / "run_manifest.json").read_text(encoding="utf-8")
    export_result = _invoke(cli, ["export", "--run-id", "e2e_crash"])
    assert export_result.exit_code == 0
    second_manifest = (run_dir / "run_manifest.json").read_text(encoding="utf-8")
    assert second_manifest == first_manifest
    assert len(list((run_dir / "approval").glob("approval.json"))) == 1
