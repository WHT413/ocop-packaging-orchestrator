from __future__ import annotations

from math import hypot, isclose
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EPSILON = 1e-6


class BoundingBox(BaseModel):
    model_config = ConfigDict(frozen=True)

    x_mm: float
    y_mm: float
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)

    @property
    def right(self) -> float:
        return self.x_mm + self.width_mm

    @property
    def bottom(self) -> float:
        return self.y_mm + self.height_mm

    @property
    def area(self) -> float:
        return self.width_mm * self.height_mm

    def contains(self, other: BoundingBox) -> bool:
        return (
            other.x_mm >= self.x_mm - EPSILON
            and other.y_mm >= self.y_mm - EPSILON
            and other.right <= self.right + EPSILON
            and other.bottom <= self.bottom + EPSILON
        )

    def intersects(self, other: BoundingBox) -> bool:
        return not (
            self.right <= other.x_mm + EPSILON
            or other.right <= self.x_mm + EPSILON
            or self.bottom <= other.y_mm + EPSILON
            or other.bottom <= self.y_mm + EPSILON
        )

    def intersection_area(self, other: BoundingBox) -> float:
        if not self.intersects(other):
            return 0.0
        return max(0.0, min(self.right, other.right) - max(self.x_mm, other.x_mm)) * max(
            0.0, min(self.bottom, other.bottom) - max(self.y_mm, other.y_mm)
        )

    def translate(self, dx_mm: float, dy_mm: float) -> BoundingBox:
        return self.model_copy(update={"x_mm": self.x_mm + dx_mm, "y_mm": self.y_mm + dy_mm})

    def scale_from_center(self, factor: float) -> BoundingBox:
        nw, nh = self.width_mm * factor, self.height_mm * factor
        return BoundingBox(
            x_mm=self.x_mm + (self.width_mm - nw) / 2,
            y_mm=self.y_mm + (self.height_mm - nh) / 2,
            width_mm=nw,
            height_mm=nh,
        )

    def clamp_to(self, canvas: BoundingBox) -> BoundingBox:
        w = min(self.width_mm, canvas.width_mm)
        h = min(self.height_mm, canvas.height_mm)
        return BoundingBox(
            x_mm=min(max(self.x_mm, canvas.x_mm), canvas.right - w),
            y_mm=min(max(self.y_mm, canvas.y_mm), canvas.bottom - h),
            width_mm=w,
            height_mm=h,
        )

    def distance_to(self, other: BoundingBox) -> float:
        dx = max(other.x_mm - self.right, self.x_mm - other.right, 0.0)
        dy = max(other.y_mm - self.bottom, self.y_mm - other.bottom, 0.0)
        return hypot(dx, dy)


class FoldLine(BaseModel):
    axis: Literal["vertical", "horizontal"]
    position_mm: float


class PanelRegion(BaseModel):
    name: str
    bbox: BoundingBox


class FoldExclusionZone(BaseModel):
    fold: FoldLine
    bbox: BoundingBox


class Canvas(BaseModel):
    bbox: BoundingBox
    panels: list[PanelRegion]
    fold_zones: list[FoldExclusionZone]
    horizontal_bands: list[BoundingBox]

    def panel_for(self, bbox: BoundingBox) -> str | None:
        for panel in self.panels:
            if panel.bbox.contains(bbox):
                return panel.name
        return None

    def crosses_vertical_fold(self, bbox: BoundingBox) -> bool:
        return any(z.fold.axis == "vertical" and bbox.intersects(z.bbox) for z in self.fold_zones)

    def crosses_horizontal_fold_band(self, bbox: BoundingBox) -> bool:
        return any(bbox.intersects(band) for band in self.horizontal_bands)

    def contains(self, bbox: BoundingBox) -> bool:
        return self.bbox.contains(bbox)


def float_eq(a: float, b: float, tol: float = EPSILON) -> bool:
    return isclose(a, b, abs_tol=tol)
