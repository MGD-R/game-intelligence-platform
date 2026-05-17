from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from src.ingestion import base_client
from src.ingestion.base_client import BaseAPIClient, CacheMissError
from src.ingestion.request_cache import ResponseCache
from src.ingestion.request_hash import build_request_hash


def _request_hash(
    *,
    source: str,
    base_url: str,
    endpoint: str,
    params: dict[str, object],
) -> str:
    return build_request_hash(
        source=source,
        endpoint=f"{base_url}{endpoint}",
        method="GET",
        params=params,
        json_body=None,
        raw_body=None,
    )


def _write_cache(
    cache_root: Path,
    *,
    source: str,
    base_url: str,
    endpoint: str,
    params: dict[str, object],
    http_status: int,
    response_json: dict[str, object],
) -> ResponseCache:
    request_hash = _request_hash(
        source=source,
        base_url=base_url,
        endpoint=endpoint,
        params=params,
    )
    cache = ResponseCache(cache_root=cache_root)
    cache.write(
        source,
        request_hash,
        {
            "source": source,
            "endpoint": "/items",
            "request_hash": request_hash,
            "http_status": http_status,
            "response_json": response_json,
            "response_hash": "resp-hash",
            "redacted_request_metadata": {"params": {}},
        },
    )
    return cache


def test_cached_200_is_returned(tmp_path: Path) -> None:
    base_url = "https://example.test"
    endpoint = "/items"
    params = {"page": 1}
    cache = _write_cache(
        tmp_path,
        source="wikidata",
        base_url=base_url,
        endpoint=endpoint,
        params=params,
        http_status=200,
        response_json={"results": ["cached"]},
    )
    client = BaseAPIClient(
        source="wikidata",
        base_url=base_url,
        cache=cache,
        repository=None,
    )

    response = client.request("GET", endpoint, params=params)

    assert response.from_cache is True
    assert response.http_status == 200
    assert response.payload == {"results": ["cached"]}


def test_cached_502_is_skipped_and_network_is_retried(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base_url = "https://example.test"
    endpoint = "/items"
    params = {"page": 1}
    cache = _write_cache(
        tmp_path,
        source="wikidata",
        base_url=base_url,
        endpoint=endpoint,
        params=params,
        http_status=502,
        response_json={"error": "bad gateway"},
    )

    class FakeHTTPClient:
        def __enter__(self) -> "FakeHTTPClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def request(self, *_args, **_kwargs) -> httpx.Response:
            request = httpx.Request("GET", "https://example.test/items?page=1")
            return httpx.Response(200, request=request, json={"results": ["fresh"]})

    monkeypatch.setattr(base_client.httpx, "Client", lambda **_: FakeHTTPClient())
    client = BaseAPIClient(
        source="wikidata",
        base_url=base_url,
        cache=cache,
        repository=None,
    )

    response = client.request("GET", endpoint, params=params)

    assert response.from_cache is False
    assert response.http_status == 200
    assert response.payload == {"results": ["fresh"]}


def test_from_cache_only_with_failed_cache_fails_clearly(tmp_path: Path) -> None:
    base_url = "https://example.test"
    endpoint = "/items"
    params = {"page": 1}
    cache = _write_cache(
        tmp_path,
        source="wikidata",
        base_url=base_url,
        endpoint=endpoint,
        params=params,
        http_status=504,
        response_json={"error": "gateway timeout"},
    )
    client = BaseAPIClient(
        source="wikidata",
        base_url=base_url,
        cache=cache,
        repository=None,
    )

    with pytest.raises(CacheMissError, match="Only failed cache entry exists"):
        client.request("GET", endpoint, params=params, from_cache_only=True)
