from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ocop_pack.schemas.design_planner import DesignPlan, LayoutIntent

TEMPLATE_CONFIG_VERSION = "template-registry.v1"


@dataclass(frozen=True)
class TemplateFamily:
    template_id: str
    family: str
    version: str
    topology: tuple[str, ...]
    slot_ownership: dict[str, str]
    hierarchy: tuple[str, ...]
    eligible_panel_strategies: tuple[str, ...]
    eligible_density: tuple[str, ...]
    eligible_hierarchy: tuple[str, ...]


class TemplateRegistry:
    """Loads approved template families; configs contain semantics, not coordinates."""

    def __init__(self, config_dir: Path = Path("configs/templates")) -> None:
        self.config_dir = config_dir
        self._families = self._load()

    def all(self) -> list[TemplateFamily]:
        return list(self._families)

    def eligible(self, plan: DesignPlan, intent: LayoutIntent) -> list[TemplateFamily]:
        matches = [family for family in self._families if _matches(family, plan, intent)]
        if matches:
            return matches
        return [
            family
            for family in self._families
            if intent.panel_strategy in family.eligible_panel_strategies
        ]

    def _load(self) -> list[TemplateFamily]:
        families: list[TemplateFamily] = []
        for path in sorted(self.config_dir.glob("*.v1.yaml")):
            data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
            if data.get("config_version") != TEMPLATE_CONFIG_VERSION:
                continue
            families.append(
                TemplateFamily(
                    template_id=str(data["template_id"]),
                    family=str(data["family"]),
                    version=str(data["version"]),
                    topology=tuple(data["topology"]),
                    slot_ownership=dict(data["slot_ownership"]),
                    hierarchy=tuple(data["hierarchy"]),
                    eligible_panel_strategies=tuple(data["eligibility"]["panel_strategy"]),
                    eligible_density=tuple(data["eligibility"]["content_density"]),
                    eligible_hierarchy=tuple(data["eligibility"]["hierarchy_model"]),
                )
            )
        return families


def _matches(family: TemplateFamily, plan: DesignPlan, intent: LayoutIntent) -> bool:
    return (
        intent.panel_strategy in family.eligible_panel_strategies
        and plan.artwork_density in family.eligible_density
        and intent.content_hierarchy in family.eligible_hierarchy
    )
