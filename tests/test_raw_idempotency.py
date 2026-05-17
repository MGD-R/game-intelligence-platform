from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.ingestion.repository import IngestionRepository


class _Cursor:
    def __init__(self) -> None:
        self.query = None
        self.params = None
        self.executemany_query = None
        self.executemany_params = None

    def __enter__(self) -> "_Cursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, query, params) -> None:  # type: ignore[no-untyped-def]
        self.query = str(query)
        self.params = params

    def executemany(self, query, params_seq) -> None:  # type: ignore[no-untyped-def]
        self.executemany_query = str(query)
        self.executemany_params = list(params_seq)


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


def test_replace_source_staging_rows_adapts_json_values(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    cursor = _Cursor()
    repository = IngestionRepository(dsn="postgresql://stub")
    monkeypatch.setattr(repository, "connection", lambda: _Connection(cursor))

    repository.replace_source_staging_rows(
        source="rawg",
        table_name="stg.source_games",
        rows=[
            {
                "source": "rawg",
                "source_game_id": "1",
                "name": "Game",
                "quality_flags_json": {"has_details": True},
                "source_specific_json": ["a", "b"],
            }
        ],
        key_columns=["source", "source_game_id"],
    )

    assert "DELETE FROM" in cursor.query
    assert "INSERT INTO" in cursor.executemany_query
    inserted_row = cursor.executemany_params[0]
    assert inserted_row[3].__class__.__name__ == "Jsonb"
    assert inserted_row[4].__class__.__name__ == "Jsonb"


def test_insert_raw_record_is_idempotent_in_postgres() -> None:
    repository = IngestionRepository()
    endpoint = "/tests/idempotency"
    request_hash = "idempotency-hash"
    source_record_id = "test-record"

    try:
        with repository.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM raw.rawg_game_index
                    WHERE endpoint = %s AND request_hash = %s AND source_record_id = %s
                    """,
                    (endpoint, request_hash, source_record_id),
                )
    except Exception as exc:  # pragma: no cover - environment-specific skip
        pytest.skip(f"postgres not available for integration test: {exc}")

    repository.insert_raw_record(
        table_name="raw.rawg_game_index",
        endpoint=endpoint,
        request_hash=request_hash,
        source_record_id=source_record_id,
        response_json={"id": 1, "name": "first"},
        response_hash="resp-a",
        response_storage_path="cache/rawg/resp-a.json",
        from_cache=False,
        http_status=200,
        error_message=None,
    )

    with repository.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, loaded_at, from_cache, response_hash
                FROM raw.rawg_game_index
                WHERE endpoint = %s AND request_hash = %s AND source_record_id = %s
                """,
                (endpoint, request_hash, source_record_id),
            )
            first_row = cursor.fetchone()

    repository.insert_raw_record(
        table_name="raw.rawg_game_index",
        endpoint=endpoint,
        request_hash=request_hash,
        source_record_id=source_record_id,
        response_json={"id": 1, "name": "second"},
        response_hash="resp-b",
        response_storage_path="cache/rawg/resp-b.json",
        from_cache=True,
        http_status=200,
        error_message=None,
    )

    with repository.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS row_count
                FROM raw.rawg_game_index
                WHERE endpoint = %s AND request_hash = %s AND source_record_id = %s
                """,
                (endpoint, request_hash, source_record_id),
            )
            count_row = cursor.fetchone()
            cursor.execute(
                """
                SELECT from_cache, response_hash, loaded_at
                FROM raw.rawg_game_index
                WHERE endpoint = %s AND request_hash = %s AND source_record_id = %s
                """,
                (endpoint, request_hash, source_record_id),
            )
            second_row = cursor.fetchone()
            cursor.execute(
                """
                DELETE FROM raw.rawg_game_index
                WHERE endpoint = %s AND request_hash = %s AND source_record_id = %s
                """,
                (endpoint, request_hash, source_record_id),
            )

    assert count_row["row_count"] == 1
    assert second_row["from_cache"] is True
    assert second_row["response_hash"] == "resp-b"
    assert isinstance(first_row["loaded_at"], datetime)
    assert isinstance(second_row["loaded_at"], datetime)
    assert second_row["loaded_at"] >= first_row["loaded_at"].astimezone(UTC)
