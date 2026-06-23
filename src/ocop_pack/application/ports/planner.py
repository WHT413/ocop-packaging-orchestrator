from __future__ import annotations

from typing import Protocol

from ocop_pack.domain.project import ProjectSpec


class DesignPlanner(Protocol):
    def create_plan(self, project: ProjectSpec) -> dict[str, object]: ...
