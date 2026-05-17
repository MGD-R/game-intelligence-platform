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


def _build_client(
    *,
    source: str,
    tmp_path,
    repository: _RepoStub | None = None,
) -> BaseAPIClient:
    return BaseAPIClient(
        source=source,
        base_url="https://example.test",
        cache=ResponseCache(cache_root=tmp_path / "cache"),
        retry_policy=RetryPolicy(max_attempts=3, sleep_fn=lambda _: None),
        repository=repository or _RepoStub(),
    )


def test_fresh_502_after_retries_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    repository = _RepoStub()
    client = _build_client(source="wikidata", tmp_path=tmp_path, repository=repository)
    calls: list[dict[str, object]] = []
    responses = [
        _response(502, "https://example.test/resource"),
        _response(502, "https://example.test/resource"),
        _response(502, "https://example.test/resource"),
    ]
    monkeypatch.setattr(
        "src.ingestion.base_client.httpx.Client",
        lambda timeout: _HTTPClientStub(responses, calls),
    )

    with pytest.raises(HTTPStatusError, match="HTTP 502"):
        client.request("GET", "/resource")

    assert len(calls) == 3
    assert repository.finished[-1]["http_status"] == 502
    assert repository.finished[-1]["error_message"] == "HTTP 502"
    cached_entry = client.cache.read("wikidata", repository.started[-1]["request_hash"])
    assert cached_entry["http_status"] == 502


def test_fresh_429_after_retries_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    repository = _RepoStub()
    client = _build_client(source="rawg", tmp_path=tmp_path, repository=repository)
    calls: list[dict[str, object]] = []
    responses = [
        _response(429, "https://example.test/resource"),
        _response(429, "https://example.test/resource"),
        _response(429, "https://example.test/resource"),
    ]
    monkeypatch.setattr(
        "src.ingestion.base_client.httpx.Client",
        lambda timeout: _HTTPClientStub(responses, calls),
    )

    with pytest.raises(HTTPStatusError, match="HTTP 429"):
        client.request("GET", "/resource")

    assert len(calls) == 3
    assert repository.finished[-1]["http_status"] == 429


def test_steam_403_is_not_retried_repeatedly(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    repository = _RepoStub()
    client = _build_client(source="steam", tmp_path=tmp_path, repository=repository)
    calls: list[dict[str, object]] = []
    responses = [_response(403, "https://example.test/appdetails")]
    monkeypatch.setattr(
        "src.ingestion.base_client.httpx.Client",
        lambda timeout: _HTTPClientStub(responses, calls),
    )

    with pytest.raises(HTTPStatusError, match="HTTP 403"):
        client.request("GET", "/appdetails")

    assert len(calls) == 1
    assert repository.finished[-1]["http_status"] == 403


def test_successful_200_still_returns_normally(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    client = _build_client(source="rawg", tmp_path=tmp_path)
    calls: list[dict[str, object]] = []
    responses = [_response(200, "https://example.test/games", {"results": [{"id": 1}]})]
    monkeypatch.setattr(
        "src.ingestion.base_client.httpx.Client",
        lambda timeout: _HTTPClientStub(responses, calls),
    )

    response = client.request("GET", "/games")

    assert response.http_status == 200
    assert response.payload == {"results": [{"id": 1}]}
    assert response.from_cache is False
    assert len(calls) == 1
