from __future__ import annotations

from src.ingestion.repository import IngestionRepository


class _Cursor:
    def __init__(self) -> None:
        self.query = None
        self.params = None

    def __enter__(self) -> "_Cursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, query, params) -> None:  # type: ignore[no-untyped-def]
        self.query = str(query)
        self.params = params


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> "_Connection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self) -> _Cursor:
        return self._cursor


def test_insert_raw_record_uses_on_conflict_update(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    cursor = _Cursor()
    repository = IngestionRepository(dsn="postgresql://stub")
    monkeypatch.setattr(repository, "connection", lambda: _Connection(cursor))

    repository.insert_raw_record(
        table_name="raw.rawg_reference_data",
        endpoint="/genres",
        request_hash="hash-1",
        source_record_id="genres",
        response_json={"results": []},
        response_hash="resp-1",
        response_storage_path="cache/rawg/hash-1.json",
        from_cache=False,
        http_status=200,
        error_message=None,
    )

    assert "ON CONFLICT" in cursor.query
    assert "response_hash = EXCLUDED.response_hash" in cursor.query
    assert cursor.params[1] == "/genres"
    assert cursor.params[2] == "hash-1"


def test_import_raw_record_maps_optional_fields(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, object] = {}
    repository = IngestionRepository(dsn="postgresql://stub")

    def fake_insert_raw_record(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)

    monkeypatch.setattr(repository, "insert_raw_record", fake_insert_raw_record)
    repository.import_raw_record(
        table_name="raw.igdb_reference_data",
        row={
            "endpoint": "/genres",
            "request_hash": "hash-2",
            "response_json": {"items": []},
            "from_cache": True,
            "http_status": 200,
        },
    )

    assert captured["table_name"] == "raw.igdb_reference_data"
    assert captured["from_cache"] is True
    assert captured["response_hash"] is None
