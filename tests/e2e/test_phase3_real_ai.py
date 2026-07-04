from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from ocop_pack.infrastructure.config import (
    ImageSettings,
    PlannerSettings,
    RealAITestSettings,
    VisionSettings,
)
from ocop_pack.orchestration.runner import WorkflowRunner
from ocop_pack.orchestration.status import RunStatus

PROJECT = Path("examples/projects/tea_basic/project.yaml")


def _real_ai_enabled() -> bool:
    return RealAITestSettings().real_ai


def _has_online_provider_config() -> bool:
    planner = PlannerSettings()
    image = ImageSettings()
    vision = VisionSettings()
    planner_ready = planner.provider == "mock" or bool(planner.base_url and planner.api_key)
    image_ready = image.provider == "openai-compatible" and bool(image.base_url and image.api_key)
    vision_ready = vision.provider == "mock" or bool(vision.base_url and vision.api_key)
    return planner_ready and image_ready and vision_ready


pytestmark = pytest.mark.real_ai


def test_phase3_online_provider_config_is_ready_for_real_image_e2e() -> None:
    if not _real_ai_enabled():
        pytest.skip("set OCOP_E2E_REAL_AI=1 to run real AI provider tests")

    planner = PlannerSettings()
    image = ImageSettings()

    assert planner.provider in {"mock", "openai-compatible"}
    if planner.provider == "openai-compatible":
        assert planner.base_url
        assert planner.api_key
    assert planner.model
    assert image.provider == "openai-compatible"
    assert image.base_url
    assert image.api_key
    assert image.model


def test_phase3_full_e2e_generates_real_ai_artwork_and_final_packaging(
    tmp_path: Path,
) -> None:
    if not _real_ai_enabled():
        pytest.skip("set OCOP_E2E_REAL_AI=1 to run real AI provider tests")
    if not _has_online_provider_config():
        pytest.skip("OCOP_PLANNER_*, OCOP_IMAGE_*, and OCOP_VISION_* online config are required")

    runner = WorkflowRunner(tmp_path, online=True)
    state = runner.start(PROJECT, "phase3_real_ai")

    assert state["status"] == RunStatus.WAITING_APPROVAL
    assert state["planner_provider"] in {"mock", "openai-compatible"}
    assert state["image_provider"] == "openai-compatible"
    assert state["llm_calls"] == 1
    assert state["image_calls"] >= 1
    assert "plan_design" in state["completed_nodes"]
    assert "generate_artworks" in state["completed_nodes"]

    artwork_paths = [Path(ref) for ref in state["artwork_refs"]]
    assert artwork_paths
    for artwork_path in artwork_paths:
        assert artwork_path.exists()
        with Image.open(artwork_path) as image:
            assert image.format == "PNG"
            assert image.size == (1024, 1024)
        provenance_path = artwork_path.with_suffix(".provenance.json")
        assert provenance_path.exists()

    approved = runner.approve(
        "phase3_real_ai", state["selected_candidate_id"] or "", approved_by="real-ai-e2e"
    )

    assert approved["status"] == RunStatus.EXPORTED
    assert Path(approved["final_png_ref"] or "").exists()
    assert Path(approved["final_pdf_ref"] or "").exists()
    with Image.open(Path(approved["final_png_ref"] or "")) as image:
        assert image.format == "PNG"
        assert image.width > 0
        assert image.height > 0
    assert "render_final_outputs" in approved["completed_nodes"]
    assert "export_bundle" in approved["completed_nodes"]
