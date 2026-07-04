from __future__ import annotations

from hashlib import sha256
from typing import Any

from ocop_pack.engine.qr import QR_POLICY_VERSION


def stable_cache_key(payload: Any) -> str:
    import json

    return sha256(
        json.dumps(
            {"qr_policy_version": QR_POLICY_VERSION, "payload": payload},
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def critic_cache_key(payload: Any) -> str:
    return stable_cache_key({"kind": "critic", "payload": payload})


def revision_cache_key(payload: Any) -> str:
    return stable_cache_key({"kind": "revision", "payload": payload})
