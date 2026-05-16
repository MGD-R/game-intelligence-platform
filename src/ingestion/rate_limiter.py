"""Synchronous reusable rate limiting utilities."""

from __future__ import annotations

import os
import time
from collections import deque
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
    request_times: deque[float] = field(default_factory=deque)

    def acquire(self) -> float:
        now = self.time_fn()
        self._prune(now)
        slept = 0.0
        if len(self.request_times) >= self.limit.requests:
            oldest = self.request_times[0]
            slept = max(0.0, self.limit.period_seconds - (now - oldest))
            if slept > 0:
                self.sleep_fn(slept)
                now = self.time_fn()
                self._prune(now)
        self.request_times.append(now)
        return slept

    def _prune(self, now: float) -> None:
        window_start = now - self.limit.period_seconds
        while self.request_times and self.request_times[0] <= window_start:
            self.request_times.popleft()


def resolve_rate_limit(source: str, settings: Mapping[str, object]) -> RateLimit | None:
    upper_source = source.upper()
    if upper_source in {"RAWG", "STEAM", "IGDB"}:
        per_second = os.getenv(f"{upper_source}_REQUESTS_PER_SECOND")
        if per_second:
            return RateLimit(requests=max(1, int(per_second)), period_seconds=1.0)

    if source.lower() in {"wikidata", "wikipedia"}:
        per_minute = os.getenv("WIKIMEDIA_REQUESTS_PER_MINUTE")
        if per_minute:
            return RateLimit(requests=max(1, int(per_minute)), period_seconds=60.0)

    configured = settings.get("rate_limit_per_minute")
    if configured:
        return RateLimit(requests=max(1, int(configured)), period_seconds=60.0)
    return None
