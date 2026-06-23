from __future__ import annotations

from ocop_pack.domain.project import ProjectSpec


class MockDesignPlanner:
    def create_plan(self, project: ProjectSpec) -> dict[str, object]:
        return {
            "provider": "mock",
            "project_id": project.project_id,
            "strategy": "deterministic_phase1_reuse",
            "note": "Phase 2 mock; replace through DesignPlanner port in Phase 3.",
        }
