from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import sleep
from typing import TypeVar

from ocop_pack.providers.common.errors import ProviderError

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 2
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 8.0
    jitter: bool = False


def run_with_retry[T](call: Callable[[], T], policy: RetryPolicy) -> tuple[T, int]:
    attempt = 1
    while True:
        try:
            return call(), attempt
        except ProviderError as exc:
            if not exc.retryable or attempt >= policy.max_attempts:
                raise
            sleep(min(policy.initial_backoff_seconds * attempt, policy.max_backoff_seconds))
            attempt += 1
