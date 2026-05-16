"""Simple in-memory rate limiter placeholder."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class RateLimiter:
    rate_limit_per_minute: int
    requests: list[float] = field(default_factory=list)

    def allow(self) -> bool:
        now = time.time()
        window_start = now - 60
        self.requests = [
            request_time for request_time in self.requests if request_time >= window_start
        ]
        if len(self.requests) >= self.rate_limit_per_minute:
            return False
        self.requests.append(now)
        return True
