from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from ocop_pack.domain.project import ProjectSpec


def load_project(path: Path) -> ProjectSpec:
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    base = path.parent
    for logo in data.get("branding", {}).get("logos", []):
        logo["path"] = str((base / logo["path"]).resolve())
    ocop = data.get("branding", {}).get("ocop", {})
    if "logo_path" in ocop:
        ocop["logo_path"] = str((base / ocop["logo_path"]).resolve())
    return ProjectSpec.model_validate(data)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def project_hash(project: ProjectSpec) -> str:
    return hashlib.sha256(project.model_dump_json().encode("utf-8")).hexdigest()
