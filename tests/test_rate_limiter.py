from src.ingestion.rate_limiter import RateLimit, RateLimiter, resolve_rate_limit


def test_rate_limiter_sleeps_when_limit_reached() -> None:
    timestamps = iter([0.0, 0.2])
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


def test_rate_limiter_spreads_requests_across_period() -> None:
    timestamps = iter([0.0, 0.1, 6.2])
    slept: list[float] = []

    limiter = RateLimiter(
        limit=RateLimit(requests=10, period_seconds=60.0),
        time_fn=lambda: next(timestamps),
        sleep_fn=slept.append,
    )

    first_sleep = limiter.acquire()
    second_sleep = limiter.acquire()
    third_sleep = limiter.acquire()

    assert first_sleep == 0.0
    assert second_sleep == 5.9
    assert third_sleep == 5.8
    assert slept == [5.9, 5.8]


def test_resolve_rate_limit_prefers_source_specific_wikipedia_env(monkeypatch) -> None:
    monkeypatch.setenv("WIKIMEDIA_REQUESTS_PER_MINUTE", "120")
    monkeypatch.setenv("WIKIPEDIA_RATE_LIMIT_PER_MINUTE", "10")

    limit = resolve_rate_limit("wikipedia", {"rate_limit_per_minute": 30})

    assert limit == RateLimit(requests=10, period_seconds=60.0)


def test_resolve_rate_limit_prefers_source_specific_wikidata_requests_env(monkeypatch) -> None:
    monkeypatch.delenv("WIKIMEDIA_REQUESTS_PER_MINUTE", raising=False)
    monkeypatch.delenv("WIKIDATA_RATE_LIMIT_PER_MINUTE", raising=False)
    monkeypatch.setenv("WIKIDATA_REQUESTS_PER_MINUTE", "15")

    limit = resolve_rate_limit("wikidata", {"requests_per_minute": 30})

    assert limit == RateLimit(requests=15, period_seconds=60.0)
