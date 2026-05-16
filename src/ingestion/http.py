"""HTTP transport helpers with controlled retry behavior."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx


@dataclass(slots=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff_seconds: float = 0.5
    max_backoff_seconds: float = 4.0
    sleep_fn: Callable[[float], None] = field(default=time.sleep)

    def backoff_seconds(self, attempt: int) -> float:
        return min(self.initial_backoff_seconds * (2 ** (attempt - 1)), self.max_backoff_seconds)


def should_retry_exception(exc: Exception) -> bool:
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError))


def should_retry_response(source: str, status_code: int) -> bool:
    if status_code == 429:
        return True
    if 500 <= status_code < 600:
        return True
    if source.lower() == "steam" and status_code == 403:
        return False
    return False


def execute_with_retry(
    send_request: Callable[[], httpx.Response],
    *,
    source: str,
    retry_policy: RetryPolicy,
) -> httpx.Response:
    for attempt in range(1, retry_policy.max_attempts + 1):
        try:
            response = send_request()
        except Exception as exc:
            if attempt >= retry_policy.max_attempts or not should_retry_exception(exc):
                raise
            retry_policy.sleep_fn(retry_policy.backoff_seconds(attempt))
            continue

        should_retry = should_retry_response(source, response.status_code)
        if should_retry and attempt < retry_policy.max_attempts:
            retry_policy.sleep_fn(retry_policy.backoff_seconds(attempt))
            continue
        return response

    raise RuntimeError("Retry loop exhausted unexpectedly")
