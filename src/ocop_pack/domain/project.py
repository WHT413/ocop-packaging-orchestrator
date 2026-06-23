from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from ocop_pack.domain.dieline import ALLOWED_SIZE_IDS

ASSET_TYPES = {"png", "jpg", "jpeg", "svg"}


class LogoAssetSpec(BaseModel):
    asset_id: str
    path: Path
    asset_type: str
    role: str = "brand"

    @field_validator("asset_type")
    @classmethod
    def valid_type(cls, value: str) -> str:
        if value.lower() not in ASSET_TYPES:
            raise ValueError("unsupported asset type")
        return value.lower()

    @field_validator("path")
    @classmethod
    def path_exists(cls, value: Path) -> Path:
        if not value.exists():
            raise ValueError(f"asset path does not exist: {value}")
        return value


class ProductSpec(BaseModel):
    name: str
    category: str
    net_content: str
    ingredients: str
    usage_instructions: str
    storage_instructions: str
    expiry_or_shelf_life: str


class ProducerSpec(BaseModel):
    manufacturer_name: str
    manufacturer_address: str
    contact_phone: str


class OcopSpec(BaseModel):
    logo_path: Path
    star_count: int = Field(ge=1, le=5)

    @field_validator("logo_path")
    @classmethod
    def ocop_exists(cls, value: Path) -> Path:
        if not value.exists():
            raise ValueError("OCOP logo is required")
        return value


class BrandSpec(BaseModel):
    logos: list[LogoAssetSpec]
    ocop: OcopSpec

    @model_validator(mode="after")
    def logo_count(self) -> BrandSpec:
        if len(self.logos) + 1 > 5:
            raise ValueError("total visible logos must not exceed 5")
        return self


class PackagingSpec(BaseModel):
    size_id: str
    qr_payload: str = "https://ocop.example.local/product"

    @field_validator("size_id")
    @classmethod
    def allowed_size(cls, value: str) -> str:
        if value not in ALLOWED_SIZE_IDS:
            raise ValueError("size_id is not supported")
        return value


class ProjectSpec(BaseModel):
    project_id: str
    product: ProductSpec
    producer: ProducerSpec
    origin_text: str
    branding: BrandSpec
    packaging: PackagingSpec

    @field_validator("project_id")
    @classmethod
    def slug_safe(cls, value: str) -> str:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", value):
            raise ValueError("project_id must be slug-safe")
        return value

    @model_validator(mode="after")
    def required_text(self) -> ProjectSpec:
        values = [self.origin_text, self.product.name, self.product.ingredients]
        if any(not v.strip() for v in values):
            raise ValueError("required content must not be empty")
        return self
