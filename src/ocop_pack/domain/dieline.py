from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ocop_pack.domain.geometry import BoundingBox, Canvas, FoldExclusionZone, FoldLine, PanelRegion

SizeId = Literal[
    "OCOP_130X150",
    "OCOP_156X180",
    "OCOP_180X120",
    "OCOP_220X140",
    "OCOP_260X160",
    "OCOP_100X100",
    "OCOP_130X130",
    "OCOP_200X150",
]
ALLOWED_SIZE_IDS = {
    "OCOP_130X150",
    "OCOP_156X180",
    "OCOP_180X120",
    "OCOP_220X140",
    "OCOP_260X160",
    "OCOP_100X100",
    "OCOP_130X130",
    "OCOP_200X150",
}


class PanelSpec(BaseModel):
    name: str
    bbox_mm: BoundingBox


class DielineSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    size_id: SizeId
    version: str
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)
    vertical_folds_x_mm: list[float] = Field(min_length=2, max_length=2)
    horizontal_folds_y_mm: list[float] = Field(min_length=2, max_length=2)
    fold_exclusion_mm: float = Field(gt=0)
    glue_flap: None = None

    @model_validator(mode="after")
    def validate_folds(self) -> DielineSpec:
        if self.vertical_folds_x_mm != sorted(self.vertical_folds_x_mm):
            raise ValueError("vertical folds must be sorted")
        if self.horizontal_folds_y_mm != sorted(self.horizontal_folds_y_mm):
            raise ValueError("horizontal folds must be sorted")
        if not all(0 < x < self.width_mm for x in self.vertical_folds_x_mm):
            raise ValueError("vertical folds must be inside canvas")
        if not all(0 < y < self.height_mm for y in self.horizontal_folds_y_mm):
            raise ValueError("horizontal folds must be inside canvas")
        return self

    def panels(self) -> list[PanelSpec]:
        x1, x2 = self.vertical_folds_x_mm
        return [
            PanelSpec(
                name="left_panel",
                bbox_mm=BoundingBox(x_mm=0, y_mm=0, width_mm=x1, height_mm=self.height_mm),
            ),
            PanelSpec(
                name="center_panel",
                bbox_mm=BoundingBox(x_mm=x1, y_mm=0, width_mm=x2 - x1, height_mm=self.height_mm),
            ),
            PanelSpec(
                name="right_panel",
                bbox_mm=BoundingBox(
                    x_mm=x2, y_mm=0, width_mm=self.width_mm - x2, height_mm=self.height_mm
                ),
            ),
        ]

    def canvas(self) -> Canvas:
        bbox = BoundingBox(x_mm=0, y_mm=0, width_mm=self.width_mm, height_mm=self.height_mm)
        zones = []
        for x in self.vertical_folds_x_mm:
            zones.append(
                FoldExclusionZone(
                    fold=FoldLine(axis="vertical", position_mm=x),
                    bbox=BoundingBox(
                        x_mm=x - self.fold_exclusion_mm,
                        y_mm=0,
                        width_mm=self.fold_exclusion_mm * 2,
                        height_mm=self.height_mm,
                    ),
                )
            )
        y1, y2 = self.horizontal_folds_y_mm
        bands = [
            BoundingBox(x_mm=0, y_mm=0, width_mm=self.width_mm, height_mm=y1),
            BoundingBox(x_mm=0, y_mm=y2, width_mm=self.width_mm, height_mm=self.height_mm - y2),
        ]
        return Canvas(
            bbox=bbox,
            panels=[PanelRegion(name=p.name, bbox=p.bbox_mm) for p in self.panels()],
            fold_zones=zones,
            horizontal_bands=bands,
        )


def load_dieline(size_id: str, config_dir: Path = Path("configs/size_profiles")) -> DielineSpec:
    if size_id not in ALLOWED_SIZE_IDS:
        raise ValueError(f"unsupported size_id: {size_id}")
    # Derive filename from size_id: OCOP_130X150 -> ocop_130x150.v2.yaml
    file_name = size_id.lower() + ".v2.yaml"
    data: dict[str, Any] = yaml.safe_load((config_dir / file_name).read_text(encoding="utf-8"))
    return DielineSpec.model_validate(data)
