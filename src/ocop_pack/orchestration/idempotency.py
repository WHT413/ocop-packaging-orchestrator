from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

CONFIG_VERSION = "phase2.v1"
RENDERER_VERSION = "renderer.v1"


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def idempotency_key(
    node_name: str,
    normalized_input_hashes: list[str],
    template_version: str = "template.v1",
    config_version: str = CONFIG_VERSION,
    renderer_version: str = RENDERER_VERSION,
) -> str:
    return stable_hash(
        {
            "node": node_name,
            "inputs": sorted(normalized_input_hashes),
            "config_version": config_version,
            "template_version": template_version,
            "renderer_version": renderer_version,
        }
    )


def completed(state_completed_nodes: list[str], node_name: str) -> bool:
    return node_name in state_completed_nodes


def mark_completed(state_completed_nodes: list[str], node_name: str) -> list[str]:
    if node_name in state_completed_nodes:
        return state_completed_nodes
    return [*state_completed_nodes, node_name]
