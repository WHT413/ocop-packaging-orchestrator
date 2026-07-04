from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from ocop_pack.orchestration.idempotency import file_hash


class LocalArtifactStore:
    """
    Stores run artifacts on the local filesystem.

    This store groups generated files under a run-specific directory, provides
    helpers for writing JSON artifacts, copies source files into the run folder,
    and creates manifest entries with SHA-256 hashes for reproducibility.

    Args:
        runs_root: Root directory that contains per-run artifact directories.

    """

    def __init__(self, runs_root: Path = Path("runs")) -> None:
        self.runs_root = runs_root

    def run_dir(self, run_id: str) -> Path:
        path = self.runs_root / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def path(self, run_id: str, relative: str) -> Path:
        return self.run_dir(run_id) / relative

    def write_json_once(self, run_id: str, relative: str, payload: Any) -> str:
        path = self.path(run_id, relative)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8"
            )
        return str(path)

    def write_json(self, run_id: str, relative: str, payload: Any) -> str:
        path = self.path(run_id, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8"
        )
        return str(path)

    def copy_once(self, run_id: str, source: Path, relative: str) -> str:
        path = self.path(run_id, relative)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, path)
        return str(path)

    def manifest_entry(self, path: Path) -> dict[str, str]:
        return {"path": str(path), "sha256": file_hash(path)}
