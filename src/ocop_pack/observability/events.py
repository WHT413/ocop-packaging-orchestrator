from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class EventLog:
    def __init__(self, runs_root: Path = Path("runs")) -> None:
        self.runs_root = runs_root

    def append(
        self,
        run_id: str,
        thread_id: str,
        node: str,
        event: str,
        status: str,
        *,
        level: str = "info",
        duration_ms: int = 0,
        artifact_ref: str | None = None,
        error_code: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        path = self.runs_root / run_id / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level,
            "run_id": run_id,
            "thread_id": thread_id,
            "node": node,
            "event": event,
            "status": status,
            "duration_ms": duration_ms,
            "artifact_ref": artifact_ref,
            "error_code": error_code,
            "extra": extra or {},
        }
        line = json.dumps(record, sort_keys=True, default=str)
        if path.exists() and line in path.read_text(encoding="utf-8").splitlines():
            return
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
