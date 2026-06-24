from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ContentAddressedCache:
    def __init__(self, root: Path = Path("data/cache")) -> None:
        self.root = root

    def read_json(self, namespace: str, key: str) -> dict[str, Any] | None:
        path = self.root / namespace / f"{key}.json"
        if not path.exists():
            return None
        return dict(json.loads(path.read_text(encoding="utf-8")))

    def write_json(self, namespace: str, key: str, payload: dict[str, Any]) -> Path:
        path = self.root / namespace / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        tmp.replace(path)
        return path
