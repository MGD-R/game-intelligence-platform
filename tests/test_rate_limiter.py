from src.ingestion.rate_limiter import RateLimit, RateLimiter


def test_rate_limiter_sleeps_when_limit_reached() -> None:
    timestamps = iter([0.0, 0.2, 1.0])
    slept: list[float] = []

    limiter = RateLimiter(
        limit=RateLimit(requests=1, period_seconds=1.0),
        time_fn=lambda: next(timestamps),
        sleep_fn=slept.append,
    )

    first_sleep = limiter.acquire()
    second_sleep = limiter.acquire()

    assert first_sleep == 0.0
    assert second_sleep == 0.8
    assert slept == [0.8]
