"""Database repository helpers for ingestion state."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from contextlib import contextmanager
from typing import Any

from psycopg import sql

from src.ingestion.redaction import redact_dsn


def resolve_database_dsn() -> str:
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return dsn
    user = os.getenv("POSTGRES_USER", "gip")
    password = os.getenv("POSTGRES_PASSWORD", "change-me")
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "gip")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def database_dsn_configured() -> bool:
    return bool(resolve_database_dsn())


def redacted_database_dsn() -> str:
    return redact_dsn(resolve_database_dsn())


class IngestionRepository:
    def __init__(self, dsn: str | None = None, connect_timeout: int | None = None) -> None:
        self.dsn = dsn or resolve_database_dsn()
        self.connect_timeout = connect_timeout or int(os.getenv("DATABASE_CONNECT_TIMEOUT", "3"))

    @contextmanager
    def connection(self):  # type: ignore[no-untyped-def]
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(
            self.dsn,
            connect_timeout=self.connect_timeout,
            row_factory=dict_row,
        ) as connection:
            yield connection

    def find_logged_request(self, source: str, request_hash: str) -> dict[str, Any] | None:
        query = """
            SELECT *
            FROM meta.api_request_log
            WHERE source = %s AND request_hash = %s
            ORDER BY started_at DESC
            LIMIT 1
        """
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (source, request_hash))
                return cursor.fetchone()

    def insert_started_request_log(
        self,
        *,
        source: str,
        endpoint: str,
        request_method: str,
        request_url: str,
        request_params_json: Mapping[str, object] | None,
        request_body: Mapping[str, object] | None,
        request_hash: str,
        from_cache: bool = False,
    ) -> str:
        from psycopg.types.json import Jsonb

        query = """
            INSERT INTO meta.api_request_log (
                source,
                endpoint,
                request_method,
                request_url,
                request_params_json,
                request_body,
                request_hash,
                from_cache
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING request_id
        """
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        source,
                        endpoint,
                        request_method,
                        request_url,
                        Jsonb(dict(request_params_json or {})),
                        (
                            json.dumps(request_body, sort_keys=True)
                            if request_body is not None
                            else None
                        ),
                        request_hash,
                        from_cache,
                    ),
                )
                row = cursor.fetchone()
                return str(row["request_id"])

    def update_finished_request_log(
        self,
        request_id: str,
        *,
        http_status: int | None,
        response_hash: str | None,
        response_storage_path: str | None,
        duration_ms: int | None,
        error_message: str | None,
    ) -> None:
        query = """
            UPDATE meta.api_request_log
            SET http_status = %s,
                response_hash = %s,
                response_storage_path = %s,
                finished_at = NOW(),
                duration_ms = %s,
                error_message = %s,
                updated_at = NOW()
            WHERE request_id = %s
        """
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        http_status,
                        response_hash,
                        response_storage_path,
                        duration_ms,
                        error_message,
                        request_id,
                    ),
                )

    def record_cache_hit(
        self,
        *,
        source: str,
        endpoint: str,
        request_method: str,
        request_url: str,
        request_params_json: Mapping[str, object] | None,
        request_body: Mapping[str, object] | None,
        request_hash: str,
        http_status: int | None = None,
        response_hash: str | None = None,
        response_storage_path: str | None = None,
    ) -> str:
        existing = self.find_logged_request(source, request_hash)
        if existing:
            query = """
                UPDATE meta.api_request_log
                SET from_cache = TRUE,
                    http_status = COALESCE(%s, http_status),
                    response_hash = COALESCE(%s, response_hash),
                    response_storage_path = COALESCE(%s, response_storage_path),
                    finished_at = COALESCE(finished_at, NOW()),
                    updated_at = NOW()
                WHERE request_id = %s
            """
            with self.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        query,
                        (
                            http_status,
                            response_hash,
                            response_storage_path,
                            existing["request_id"],
                        ),
                    )
            return str(existing["request_id"])

        request_id = self.insert_started_request_log(
            source=source,
            endpoint=endpoint,
            request_method=request_method,
            request_url=request_url,
            request_params_json=request_params_json,
            request_body=request_body,
            request_hash=request_hash,
            from_cache=True,
        )
        self.update_finished_request_log(
            request_id,
            http_status=http_status,
            response_hash=response_hash,
            response_storage_path=response_storage_path,
            duration_ms=0,
            error_message=None,
        )
        return request_id

    def increment_quota_usage(
        self,
        *,
        source: str,
        quota_period: str,
        amount: int = 1,
        quota_limit: int | None = None,
    ) -> None:
        query = """
            INSERT INTO meta.api_quota_usage (source, quota_period, request_count, quota_limit)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (source, quota_period)
            DO UPDATE
            SET request_count = meta.api_quota_usage.request_count + EXCLUDED.request_count,
                quota_limit = COALESCE(EXCLUDED.quota_limit, meta.api_quota_usage.quota_limit),
                updated_at = NOW()
        """
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (source, quota_period, amount, quota_limit))

    def read_quota_usage(self, source: str, quota_period: str) -> dict[str, Any] | None:
        query = """
            SELECT source, quota_period, request_count, quota_limit, updated_at
            FROM meta.api_quota_usage
            WHERE source = %s AND quota_period = %s
        """
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (source, quota_period))
                return cursor.fetchone()

    def upsert_pipeline_run_state(
        self,
        *,
        run_id: str,
        pipeline_name: str,
        stage_name: str,
        status: str,
        duration_ms: int | None = None,
        parameters_json: Mapping[str, object] | None = None,
        metrics_json: Mapping[str, object] | None = None,
        error_message: str | None = None,
        finished: bool = False,
    ) -> None:
        from psycopg.types.json import Jsonb

        query = """
            INSERT INTO meta.pipeline_run_log (
                run_id,
                pipeline_name,
                stage_name,
                status,
                duration_ms,
                parameters_json,
                metrics_json,
                error_message,
                finished_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CASE WHEN %s THEN NOW() ELSE NULL END)
            ON CONFLICT (run_id)
            DO UPDATE
            SET pipeline_name = EXCLUDED.pipeline_name,
                stage_name = EXCLUDED.stage_name,
                status = EXCLUDED.status,
                duration_ms = EXCLUDED.duration_ms,
                parameters_json = EXCLUDED.parameters_json,
                metrics_json = EXCLUDED.metrics_json,
                error_message = EXCLUDED.error_message,
                finished_at = CASE WHEN %s THEN NOW() ELSE meta.pipeline_run_log.finished_at END,
                updated_at = NOW()
        """
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        run_id,
                        pipeline_name,
                        stage_name,
                        status,
                        duration_ms,
                        Jsonb(dict(parameters_json or {})),
                        Jsonb(dict(metrics_json or {})),
                        error_message,
                        finished,
                        finished,
                    ),
                )

    def upsert_ingestion_checkpoint(
        self,
        *,
        source: str,
        job_name: str,
        checkpoint_key: str,
        checkpoint_value: Mapping[str, object] | None,
    ) -> None:
        from psycopg.types.json import Jsonb

        query = """
            INSERT INTO meta.ingestion_checkpoint (
                source,
                job_name,
                checkpoint_key,
                checkpoint_value
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (source, job_name, checkpoint_key)
            DO UPDATE
            SET checkpoint_value = EXCLUDED.checkpoint_value,
                updated_at = NOW()
        """
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (source, job_name, checkpoint_key, Jsonb(dict(checkpoint_value or {}))),
                )

    def insert_raw_record(
        self,
        *,
        table_name: str,
        endpoint: str,
        request_hash: str,
        source_record_id: str | None,
        response_json: Mapping[str, object] | None,
        response_hash: str | None,
        response_storage_path: str | None,
        from_cache: bool,
        http_status: int | None,
        error_message: str | None,
        request_id: str | None = None,
    ) -> None:
        from psycopg.types.json import Jsonb

        schema_name, table = table_name.split(".", maxsplit=1)
        query = sql.SQL(
            """
            INSERT INTO {table} (
                request_id,
                endpoint,
                request_hash,
                source_record_id,
                response_json,
                response_hash,
                response_storage_path,
                from_cache,
                http_status,
                error_message
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
        ).format(table=sql.Identifier(schema_name, table))
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        request_id,
                        endpoint,
                        request_hash,
                        source_record_id,
                        Jsonb(dict(response_json or {})),
                        response_hash,
                        response_storage_path,
                        from_cache,
                        http_status,
                        error_message,
                    ),
                )

    def fetch_raw_rows(self, table_name: str) -> list[dict[str, Any]]:
        schema_name, table = table_name.split(".", maxsplit=1)
        query = sql.SQL(
            """
            SELECT *
            FROM {table}
            WHERE http_status IS NULL OR http_status < 400
            ORDER BY loaded_at ASC, id ASC
            """
        ).format(table=sql.Identifier(schema_name, table))
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                return list(cursor.fetchall())

    def replace_source_staging_rows(
        self,
        *,
        source: str,
        table_name: str,
        rows: list[Mapping[str, object]],
        key_columns: list[str],
    ) -> None:
        schema_name, table = table_name.split(".", maxsplit=1)
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("DELETE FROM {table} WHERE source = %s").format(
                        table=sql.Identifier(schema_name, table)
                    ),
                    (source,),
                )
                if not rows:
                    return

                columns = list(rows[0].keys())
                insert_query = sql.SQL("INSERT INTO {table} ({columns}) VALUES ({values})").format(
                    table=sql.Identifier(schema_name, table),
                    columns=sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                    values=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
                )
                cursor.executemany(
                    insert_query,
                    [tuple(row[column] for column in columns) for row in rows],
                )
