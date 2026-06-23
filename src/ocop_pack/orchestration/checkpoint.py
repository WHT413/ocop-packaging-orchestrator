from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from ocop_pack.orchestration.state import PackagingState


def _dump_state(state: PackagingState) -> dict[str, Any]:
    return {
        key: value.model_dump(mode="json") if hasattr(value, "model_dump") else value
        for key, value in state.items()
        if key != "project"
    }


class CheckpointStore(Protocol):
    def save(self, run_id: str, state: PackagingState) -> None: ...

    def load(self, run_id: str) -> dict[str, Any] | None: ...


class InMemoryCheckpointStore:
    def __init__(self) -> None:
        self._states: dict[str, dict[str, Any]] = {}

    def save(self, run_id: str, state: PackagingState) -> None:
        self._states[run_id] = _dump_state(state)

    def load(self, run_id: str) -> dict[str, Any] | None:
        return self._states.get(run_id)


class LocalCheckpointStore:
    def __init__(self, runs_root: Path = Path("runs")) -> None:
        self.runs_root = runs_root

    def _path(self, run_id: str) -> Path:
        return self.runs_root / run_id / "checkpoints" / "state.json"

    def save(self, run_id: str, state: PackagingState) -> None:
        path = self._path(run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_dump_state(state), indent=2, sort_keys=True), encoding="utf-8")

    def load(self, run_id: str) -> dict[str, Any] | None:
        path = self._path(run_id)
        if not path.exists():
            return None
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            return None
        return loaded
