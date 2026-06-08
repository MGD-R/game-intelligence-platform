"""Synchronous reusable rate limiting utilities."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RateLimit:
    requests: int
    period_seconds: float


@dataclass(slots=True)
class RateLimiter:
    limit: RateLimit
    time_fn: Callable[[], float] = time.monotonic
    sleep_fn: Callable[[float], None] = time.sleep
    next_allowed_at: float | None = field(default=None)

    def acquire(self) -> float:
        now = self.time_fn()
        slept = 0.0
        if self.next_allowed_at is not None and now < self.next_allowed_at:
            slept = self.next_allowed_at - now
            self.sleep_fn(slept)
            now += slept
        min_interval = self.limit.period_seconds / self.limit.requests
        self.next_allowed_at = now + min_interval
        return slept


def resolve_rate_limit(source: str, settings: Mapping[str, object]) -> RateLimit | None:
    upper_source = source.upper()
    if upper_source in {"RAWG", "STEAM", "IGDB"}:
        per_second = os.getenv(f"{upper_source}_REQUESTS_PER_SECOND")
        if per_second:
            return RateLimit(requests=max(1, int(per_second)), period_seconds=1.0)

    if source.lower() in {"wikidata", "wikipedia"}:
        source_per_minute = os.getenv(f"{upper_source}_RATE_LIMIT_PER_MINUTE")
        if source_per_minute:
            return RateLimit(requests=max(1, int(source_per_minute)), period_seconds=60.0)

        source_requests_per_minute = os.getenv(f"{upper_source}_REQUESTS_PER_MINUTE")
        if source_requests_per_minute:
            return RateLimit(
                requests=max(1, int(source_requests_per_minute)),
                period_seconds=60.0,
            )

        per_minute = os.getenv("WIKIMEDIA_REQUESTS_PER_MINUTE")
        if per_minute:
            return RateLimit(requests=max(1, int(per_minute)), period_seconds=60.0)

    configured = settings.get("rate_limit_per_minute")
    if not configured:
        configured = settings.get("requests_per_minute")
    if configured:
        return RateLimit(requests=max(1, int(configured)), period_seconds=60.0)
    return None
