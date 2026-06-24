from __future__ import annotations

from hashlib import sha256
from typing import Any


def stable_cache_key(payload: Any) -> str:
    import json

    return sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
