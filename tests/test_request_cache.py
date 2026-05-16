from pathlib import Path

from src.ingestion.request_cache import ResponseCache


def test_response_cache_round_trip(tmp_path: Path) -> None:
    cache = ResponseCache(cache_root=tmp_path)
    payload = {
        "source": "rawg",
        "endpoint": "/games",
        "request_hash": "abc123",
        "http_status": 200,
        "response_json": {"results": []},
        "response_hash": "hash",
        "redacted_request_metadata": {"params": {"key": "***REDACTED***"}},
    }

    path = cache.write("rawg", "abc123", payload)

    assert cache.exists("rawg", "abc123")
    assert path == tmp_path / "rawg" / "abc123.json"
    assert cache.read("rawg", "abc123")["response_json"] == {"results": []}


def test_response_cache_list_entries(tmp_path: Path) -> None:
    cache = ResponseCache(cache_root=tmp_path)
    cache.write("rawg", "one", {"source": "rawg"})
    cache.write("wikidata", "two", {"source": "wikidata"})

    assert [entry.name for entry in cache.list_entries("rawg")] == ["one.json"]
    assert sorted(entry.name for entry in cache.list_entries()) == ["one.json", "two.json"]
