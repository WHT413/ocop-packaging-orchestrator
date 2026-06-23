from __future__ import annotations

import hashlib
import os
from pathlib import Path


class LocalArtifactStorage:
    def __init__(self, root: Path = Path("runs")) -> None:
        self.root = root

    def run_dir(self, run_id: str) -> Path:
        if ".." in run_id or "/" in run_id or "\\" in run_id:
            raise ValueError("unsafe run_id")
        path = self.root / run_id
        for sub in ["input", "geometry", "candidates", "previews", "internal", "final", "qa"]:
            (path / sub).mkdir(parents=True, exist_ok=True)
        return path

    def atomic_write(
        self, run_id: str, rel: str, data: bytes, overwrite: bool = True
    ) -> tuple[str, str]:
        base = self.run_dir(run_id).resolve()
        target = (base / rel).resolve()
        if not str(target).startswith(str(base)):
            raise ValueError("path traversal blocked")
        if target.exists() and not overwrite:
            raise FileExistsError(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, target)
        return str(target.relative_to(self.root)), hashlib.sha256(data).hexdigest()

    def checksum(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
