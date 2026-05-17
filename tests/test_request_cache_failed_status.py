from __future__ import annotations

import httpx
import pytest

from src.ingestion.base_client import BaseAPIClient, HTTPStatusError
from src.ingestion.http import RetryPolicy
from src.ingestion.request_cache import ResponseCache


class _RepoStub:
    def __init__(self) -> None:
        self.started: list[dict[str, object]] = []
        self.finished: list[dict[str, object]] = []

    def insert_started_request_log(self, **kwargs):  # type: ignore[no-untyped-def]
        self.started.append(kwargs)
        return "req-1"

    def update_finished_request_log(self, request_id: str, **kwargs):  # type: ignore[no-untyped-def]
        self.finished.append({"request_id": request_id, **kwargs})


class _HTTPClientStub:
    def __init__(self, responses: list[httpx.Response], calls: list[dict[str, object]]) -> None:
        self.responses = responses
        self.calls = calls

    def __enter__(self) -> _HTTPClientStub:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:  # type: ignore[no-untyped-def]
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)


def _response(
    status_code: int,
    url: str,
    payload: dict[str, object] | None = None,
) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=payload or {"status": status_code},
        request=httpx.Request("GET", url),
    )


def test_failed_cache_entry_is_ignored_and_network_request_is_attempted(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cache = ResponseCache(cache_root=tmp_path / "cache")
    client = BaseAPIClient(
        source="wikidata",
        base_url="https://example.test",
        cache=cache,
        retry_policy=RetryPolicy(max_attempts=3, sleep_fn=lambda _: None),
        repository=_RepoStub(),
    )
    cached = client.request("GET", "/resource", dry_run=True)
    cache.write(
        "wikidata",
        cached.request_hash,
        {
            "source": "wikidata",
            "endpoint": "/resource",
            "request_hash": cached.request_hash,
            "created_at": "2026-05-17T00:00:00+00:00",
            "http_status": 502,
            "response_json": {"error": "bad gateway"},
            "response_text": None,
            "response_hash": "cached-502",
            "redacted_request_metadata": cached.request_metadata,
        },
    )
    calls: list[dict[str, object]] = []
    responses = [_response(200, "https://example.test/resource", {"ok": True})]
    monkeypatch.setattr(
        "src.ingestion.base_client.httpx.Client",
        lambda timeout: _HTTPClientStub(responses, calls),
    )

    response = client.request("GET", "/resource")

    assert response.http_status == 200
    assert response.from_cache is False
    assert response.payload == {"ok": True}
    assert len(calls) == 1


def test_from_cache_only_fails_clearly_for_failed_cached_response(tmp_path) -> None:
    cache = ResponseCache(cache_root=tmp_path / "cache")
    client = BaseAPIClient(
        source="wikidata",
        base_url="https://example.test",
        cache=cache,
        retry_policy=RetryPolicy(max_attempts=3, sleep_fn=lambda _: None),
        repository=_RepoStub(),
    )
    cached = client.request("GET", "/resource", dry_run=True)
    cache.write(
        "wikidata",
        cached.request_hash,
        {
            "source": "wikidata",
            "endpoint": "/resource",
            "request_hash": cached.request_hash,
            "created_at": "2026-05-17T00:00:00+00:00",
            "http_status": 504,
            "response_json": {"error": "timeout"},
            "response_text": None,
            "response_hash": "cached-504",
            "redacted_request_metadata": cached.request_metadata,
        },
    )

    with pytest.raises(HTTPStatusError, match="HTTP 504"):
        client.request("GET", "/resource", from_cache_only=True)
