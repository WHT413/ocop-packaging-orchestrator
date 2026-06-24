from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ocop_pack.domain.project import ProjectSpec
from ocop_pack.schemas.design_planner import DesignPlan


@dataclass(frozen=True)
class PlanValidationError:
    code: str
    message: str


class FactGetter(Protocol):
    def __call__(self, project: ProjectSpec) -> str: ...


def _product_name(project: ProjectSpec) -> str:
    return project.product.name


def _ingredients(project: ProjectSpec) -> str:
    return project.product.ingredients


def _manufacturer_name(project: ProjectSpec) -> str:
    return project.producer.manufacturer_name


def _manufacturer_address(project: ProjectSpec) -> str:
    return project.producer.manufacturer_address


def _contact_phone(project: ProjectSpec) -> str:
    return project.producer.contact_phone


def _qr_payload(project: ProjectSpec) -> str:
    return project.packaging.qr_payload


IMMUTABLE_FACT_NAMES: dict[str, FactGetter] = {
    "product_name": _product_name,
    "ingredients": _ingredients,
    "manufacturer_name": _manufacturer_name,
    "manufacturer_address": _manufacturer_address,
    "contact_phone": _contact_phone,
    "qr_payload": _qr_payload,
}


def validate_immutable_facts(project: ProjectSpec, plan: DesignPlan) -> list[PlanValidationError]:
    text = plan.model_dump_json().lower()
    errors: list[PlanValidationError] = []
    for name, getter in IMMUTABLE_FACT_NAMES.items():
        fact = getter(project).strip()
        if fact and fact.lower() in text:
            errors.append(PlanValidationError("IMMUTABLE_FACT_REWRITTEN", name))
    return errors
