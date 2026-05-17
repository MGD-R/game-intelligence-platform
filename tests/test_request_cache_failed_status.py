from __future__ import annotations

from pathlib import Path

import pytest

from src.ingestion import base_client
from src.ingestion.base_client import BaseAPIClient, CacheMissError
from src.ingestion.request_cache import ResponseCache
from src.ingestion.request_hash import build_request_hash


class DummyResponse:
    def __init__(self, *, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> object:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class DummyClient:
    def __init__(self, response: DummyResponse | None, calls: list[tuple[str, str]]) -> None:
        self.response = response
        self.calls = calls

    def __enter__(self) -> DummyClient:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def request(self, method: str, url: str, **_: object) -> DummyResponse:
        self.calls.append((method, url))
        assert self.response is not None
        return self.response


def build_client(tmp_path: Path) -> BaseAPIClient:
    return BaseAPIClient(
        source="wikidata",
        base_url="https://example.test",
        cache=ResponseCache(cache_root=tmp_path),
        repository=None,
    )


def build_cached_request_hash(*, query: str) -> str:
    return build_request_hash(
        source="wikidata",
        endpoint="https://example.test/sparql",
        method="GET",
        params={"query": query, "format": "json"},
        json_body=None,
        raw_body=None,
    )


def test_cached_success_response_is_returned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = build_client(tmp_path)
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        base_client.httpx,
        "Client",
        lambda timeout: DummyClient(None, calls),
    )
    monkeypatch.setattr(base_client, "execute_with_retry", lambda func, **_: func())
    request_hash = build_cached_request_hash(query="SELECT * WHERE { ?s ?p ?o }")

    cache_path = client.cache.cache_path("wikidata", request_hash)
    client.cache.write(
        "wikidata",
        request_hash,
        {
            "source": "wikidata",
            "endpoint": "/sparql",
            "request_hash": request_hash,
            "http_status": 200,
            "response_json": {"results": {"bindings": []}},
            "response_hash": "cached-ok",
        },
    )

    cached = client.request(
        "GET",
        "/sparql",
        params={"query": "SELECT * WHERE { ?s ?p ?o }", "format": "json"},
        use_cache=True,
    )

    assert cache_path.exists()
    assert cached.from_cache is True
    assert cached.http_status == 200
    assert cached.payload == {"results": {"bindings": []}}
    assert calls == []


def test_cached_failed_response_is_ignored_and_network_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = build_client(tmp_path)
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        base_client.httpx,
        "Client",
        lambda timeout: DummyClient(
            DummyResponse(status_code=200, payload={"results": {"bindings": [{"id": 1}]}}),
            calls,
        ),
    )
    monkeypatch.setattr(base_client, "execute_with_retry", lambda func, **_: func())
    request_hash = build_cached_request_hash(query="SELECT ?game WHERE { ?game ?p ?o }")

    client.cache.write(
        "wikidata",
        request_hash,
        {
            "source": "wikidata",
            "endpoint": "/sparql",
            "request_hash": request_hash,
            "http_status": 502,
            "response_json": {"error": "bad gateway"},
            "response_hash": "cached-bad",
        },
    )

    response = client.request(
        "GET",
        "/sparql",
        params={"query": "SELECT ?game WHERE { ?game ?p ?o }", "format": "json"},
        use_cache=True,
    )

    assert response.from_cache is False
    assert response.http_status == 200
    assert response.payload == {"results": {"bindings": [{"id": 1}]}}
    assert len(calls) == 1


def test_from_cache_only_with_failed_cached_response_fails_clearly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = build_client(tmp_path)
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        base_client.httpx,
        "Client",
        lambda timeout: DummyClient(None, calls),
    )
    monkeypatch.setattr(base_client, "execute_with_retry", lambda func, **_: func())
    request_hash = build_cached_request_hash(query="SELECT ?qid WHERE { ?qid ?p ?o }")

    client.cache.write(
        "wikidata",
        request_hash,
        {
            "source": "wikidata",
            "endpoint": "/sparql",
            "request_hash": request_hash,
            "http_status": 504,
            "response_json": {"error": "gateway timeout"},
            "response_hash": "cached-timeout",
        },
    )

    with pytest.raises(CacheMissError, match="Cached failed response"):
        client.request(
            "GET",
            "/sparql",
            params={"query": "SELECT ?qid WHERE { ?qid ?p ?o }", "format": "json"},
            use_cache=True,
            from_cache_only=True,
        )

    assert calls == []
