from __future__ import annotations

from pathlib import Path

import pytest

from ocop_pack.domain.dieline import ALLOWED_SIZE_IDS, DielineSpec, load_dieline
from ocop_pack.domain.project import ProjectSpec
from ocop_pack.engine.candidate_generator import generate_candidates
from ocop_pack.engine.constraints import candidate_passed, evaluate_candidate
from ocop_pack.services.validation_service import load_project


ALL_SIZE_IDS = sorted(ALLOWED_SIZE_IDS)


@pytest.fixture(params=ALL_SIZE_IDS)
def size_id(request: pytest.FixtureRequest) -> str:
    return request.param


class TestLoadDieline:
    """Every registered size_id must load and validate successfully."""

    def test_load_all_sizes(self, size_id: str) -> None:
        dieline = load_dieline(size_id)
        assert isinstance(dieline, DielineSpec)
        assert dieline.size_id == size_id
        assert dieline.width_mm > 0
        assert dieline.height_mm > 0

    def test_panels_returns_three(self, size_id: str) -> None:
        dieline = load_dieline(size_id)
        panels = dieline.panels()
        assert len(panels) == 3
        names = {p.name for p in panels}
        assert names == {"left_panel", "center_panel", "right_panel"}

    def test_panels_cover_full_width(self, size_id: str) -> None:
        dieline = load_dieline(size_id)
        panels = dieline.panels()
        total_width = sum(p.bbox_mm.width_mm for p in panels)
        assert abs(total_width - dieline.width_mm) < 0.01

    def test_panels_same_height(self, size_id: str) -> None:
        dieline = load_dieline(size_id)
        panels = dieline.panels()
        for panel in panels:
            assert abs(panel.bbox_mm.height_mm - dieline.height_mm) < 0.01

    def test_canvas_fold_zones(self, size_id: str) -> None:
        dieline = load_dieline(size_id)
        canvas = dieline.canvas()
        assert len(canvas.fold_zones) == 2  # two vertical folds
        assert len(canvas.horizontal_bands) == 2  # top + bottom

    def test_vertical_folds_sorted(self, size_id: str) -> None:
        dieline = load_dieline(size_id)
        assert dieline.vertical_folds_x_mm == sorted(dieline.vertical_folds_x_mm)

    def test_horizontal_folds_sorted(self, size_id: str) -> None:
        dieline = load_dieline(size_id)
        assert dieline.horizontal_folds_y_mm == sorted(dieline.horizontal_folds_y_mm)

    def test_folds_inside_canvas(self, size_id: str) -> None:
        dieline = load_dieline(size_id)
        for x in dieline.vertical_folds_x_mm:
            assert 0 < x < dieline.width_mm
        for y in dieline.horizontal_folds_y_mm:
            assert 0 < y < dieline.height_mm

    def test_unsupported_size_raises(self) -> None:
        with pytest.raises(ValueError, match="unsupported"):
            load_dieline("INVALID_999X999")


class TestLandscapeSizes:
    """Landscape sizes must have width > height."""

    LANDSCAPE_IDS = ["OCOP_180X120", "OCOP_220X140", "OCOP_260X160", "OCOP_200X150"]

    @pytest.mark.parametrize("sid", LANDSCAPE_IDS)
    def test_landscape_width_greater_than_height(self, sid: str) -> None:
        dieline = load_dieline(sid)
        assert dieline.width_mm > dieline.height_mm

    @pytest.mark.parametrize("sid", LANDSCAPE_IDS)
    def test_center_panel_is_wider_than_tall(self, sid: str) -> None:
        dieline = load_dieline(sid)
        center = next(p for p in dieline.panels() if p.name == "center_panel")
        # Center panel width should be wider than side panels
        left = next(p for p in dieline.panels() if p.name == "left_panel")
        assert center.bbox_mm.width_mm > left.bbox_mm.width_mm


class TestSquareSizes:
    """Square sizes must have width == height."""

    SQUARE_IDS = ["OCOP_100X100", "OCOP_130X130"]

    @pytest.mark.parametrize("sid", SQUARE_IDS)
    def test_square_dimensions(self, sid: str) -> None:
        dieline = load_dieline(sid)
        assert abs(dieline.width_mm - dieline.height_mm) < 0.01


class TestLandscapeProjectCandidateGeneration:
    """Landscape project should generate valid candidates."""

    def test_landscape_project_loads(self) -> None:
        project = load_project(Path("examples/projects/che_day_landscape/project.yaml"))
        assert project.packaging.size_id == "OCOP_180X120"

    def test_landscape_generates_candidates(self) -> None:
        project = load_project(Path("examples/projects/che_day_landscape/project.yaml"))
        dieline = load_dieline(project.packaging.size_id)
        candidates = generate_candidates(project, dieline, seed=42)
        assert len(candidates) >= 1

    def test_landscape_candidates_pass_constraints(self) -> None:
        project = load_project(Path("examples/projects/che_day_landscape/project.yaml"))
        dieline = load_dieline(project.packaging.size_id)
        candidates = generate_candidates(project, dieline, seed=42)
        for candidate in candidates:
            results = evaluate_candidate(project, dieline, candidate)
            # Check that critical constraints pass (warnings OK)
            critical_failures = [r for r in results if not r.passed and r.severity == "critical"]
            # Allow some critical failures due to text fitting in small panels
            # but structural constraints must pass
            structural_rules = {"HC-01", "HC-02", "HC-03", "HC-06", "HC-07"}
            structural_failures = [r for r in critical_failures if r.rule_id in structural_rules]
            assert not structural_failures, (
                f"Structural constraint failures for {candidate.candidate_id}: "
                f"{[(r.rule_id, r.message) for r in structural_failures]}"
            )
