"""Database repository helpers for ingestion state."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from contextlib import contextmanager
from typing import Any

from psycopg import sql

from src.ingestion.redaction import redact_dsn

RAW_TABLE_CONFLICT_KEYS: dict[str, list[str]] = {
    "raw.rawg_game_index": ["source", "endpoint", "request_hash", "source_record_id"],
    "raw.rawg_game_details": ["source", "endpoint", "request_hash"],
    "raw.rawg_reference_data": ["source", "endpoint", "request_hash"],
    "raw.wikidata_sparql_results": ["source", "endpoint", "request_hash"],
    "raw.wikidata_entities": ["source", "endpoint", "request_hash", "source_record_id"],
    "raw.steam_app_details": ["source", "endpoint", "request_hash", "source_record_id"],
    "raw.wikipedia_pages": ["source", "endpoint", "request_hash", "source_record_id"],
    "raw.igdb_games": ["source", "endpoint", "request_hash", "source_record_id"],
    "raw.igdb_reference_data": ["source", "endpoint", "request_hash"],
    "raw.igdb_search_results": ["source", "endpoint", "request_hash", "source_record_id"],
}


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


def _adapt_staging_value(value: object) -> object:
    from psycopg.types.json import Jsonb

    if isinstance(value, dict):
        return Jsonb(value)
    if isinstance(value, list):
        return Jsonb(value)
    return value


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
            ON CONFLICT (source, request_hash)
            WHERE request_hash IS NOT NULL
            DO UPDATE
            SET endpoint = EXCLUDED.endpoint,
                request_method = EXCLUDED.request_method,
                request_url = EXCLUDED.request_url,
                request_params_json = EXCLUDED.request_params_json,
                request_body = EXCLUDED.request_body,
                from_cache = EXCLUDED.from_cache,
                http_status = NULL,
                response_hash = NULL,
                response_storage_path = NULL,
                started_at = NOW(),
                finished_at = NULL,
                duration_ms = NULL,
                error_message = NULL,
                updated_at = NOW()
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
        conflict_columns = RAW_TABLE_CONFLICT_KEYS.get(table_name)
        if not conflict_columns:
            raise ValueError(f"Unsupported raw table for idempotent insert: {table_name}")
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
            ON CONFLICT ({conflict_columns})
            DO UPDATE
            SET request_id = EXCLUDED.request_id,
                response_json = EXCLUDED.response_json,
                response_hash = EXCLUDED.response_hash,
                response_storage_path = EXCLUDED.response_storage_path,
                loaded_at = NOW(),
                from_cache = EXCLUDED.from_cache,
                http_status = EXCLUDED.http_status,
                error_message = EXCLUDED.error_message
            """
        ).format(
            table=sql.Identifier(schema_name, table),
            conflict_columns=sql.SQL(", ").join(
                sql.Identifier(column) for column in conflict_columns
            ),
        )
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

    def import_raw_record(
        self,
        *,
        table_name: str,
        row: Mapping[str, object],
    ) -> None:
        self.insert_raw_record(
            table_name=table_name,
            endpoint=str(row.get("endpoint") or ""),
            request_hash=str(row.get("request_hash") or ""),
            source_record_id=(
                str(row.get("source_record_id"))
                if row.get("source_record_id") not in (None, "")
                else None
            ),
            response_json=(
                row.get("response_json") if isinstance(row.get("response_json"), Mapping) else {}
            ),
            response_hash=str(row.get("response_hash") or "") or None,
            response_storage_path=str(row.get("response_storage_path") or "") or None,
            from_cache=bool(row.get("from_cache")),
            http_status=int(row["http_status"]) if row.get("http_status") is not None else None,
            error_message=str(row.get("error_message") or "") or None,
            request_id=str(row.get("request_id") or "") or None,
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

    def fetch_staging_rows(
        self,
        table_name: str,
        *,
        source: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        schema_name, table = table_name.split(".", maxsplit=1)
        clauses = [sql.SQL("1 = 1")]
        params: list[object] = []
        if source is not None:
            clauses.append(sql.SQL("source = %s"))
            params.append(source)
        limit_sql = sql.SQL("")
        if limit is not None:
            limit_sql = sql.SQL(" LIMIT %s")
            params.append(limit)
        query = (
            sql.SQL(
                """
            SELECT *
            FROM {table}
            WHERE {where_clause}
            ORDER BY 1, 2
            """
            ).format(
                table=sql.Identifier(schema_name, table),
                where_clause=sql.SQL(" AND ").join(clauses),
            )
            + limit_sql
        )
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return list(cursor.fetchall())

    def count_rows(self, table_name: str, *, source: str | None = None) -> int:
        schema_name, table = table_name.split(".", maxsplit=1)
        clauses = [sql.SQL("1 = 1")]
        params: list[object] = []
        if source is not None:
            clauses.append(sql.SQL("source = %s"))
            params.append(source)
        query = sql.SQL(
            """
            SELECT COUNT(*) AS row_count
            FROM {table}
            WHERE {where_clause}
            """
        ).format(
            table=sql.Identifier(schema_name, table),
            where_clause=sql.SQL(" AND ").join(clauses),
        )
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                row = cursor.fetchone()
                return int(row["row_count"])

    def count_api_requests(self, source: str) -> int:
        query = """
            SELECT COUNT(*) AS row_count
            FROM meta.api_request_log
            WHERE source = %s
        """
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (source,))
                row = cursor.fetchone()
                return int(row["row_count"])

    def fetch_existing_tables(self, *, schemas: list[str]) -> set[tuple[str, str]]:
        query = """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
              AND table_schema = ANY(%s)
        """
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (schemas,))
                return {(row["table_schema"], row["table_name"]) for row in cursor.fetchall()}

    def upsert_candidate_pair(
        self,
        *,
        source_a: str,
        source_id_a: str,
        source_b: str,
        source_id_b: str,
        candidate_source: str | None,
        label_source: str | None,
        label_value: str | None,
        confidence: float | None,
    ) -> str:
        query = """
            INSERT INTO ml.entity_candidate_pairs (
                source_a,
                source_id_a,
                source_b,
                source_id_b,
                candidate_source,
                label_source,
                label_value,
                confidence
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_a, source_id_a, source_b, source_id_b)
            DO UPDATE
            SET candidate_source = CASE
                    WHEN ml.entity_candidate_pairs.label_value IS NOT NULL
                        THEN ml.entity_candidate_pairs.candidate_source
                    ELSE COALESCE(
                        ml.entity_candidate_pairs.candidate_source,
                        EXCLUDED.candidate_source
                    )
                END,
                label_source = COALESCE(
                    ml.entity_candidate_pairs.label_source,
                    EXCLUDED.label_source
                ),
                label_value = COALESCE(ml.entity_candidate_pairs.label_value, EXCLUDED.label_value),
                confidence = GREATEST(
                    COALESCE(ml.entity_candidate_pairs.confidence, 0),
                    COALESCE(EXCLUDED.confidence, 0)
                )
            RETURNING pair_id
        """
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        source_a,
                        source_id_a,
                        source_b,
                        source_id_b,
                        candidate_source,
                        label_source,
                        label_value,
                        confidence,
                    ),
                )
                row = cursor.fetchone()
                return str(row["pair_id"])

    def fetch_candidate_pairs(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT *
            FROM ml.entity_candidate_pairs
            ORDER BY created_at ASC, pair_id ASC
        """
        params: tuple[object, ...] = ()
        if limit is not None:
            query += " LIMIT %s"
            params = (limit,)
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return list(cursor.fetchall())

    def delete_candidate_pairs(self) -> None:
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM ml.entity_candidate_pairs")

    def delete_entity_resolution_features(self) -> None:
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM ml.entity_resolution_features")

    def ensure_entity_resolution_feature_columns(self) -> None:
        query = """
            ALTER TABLE ml.entity_resolution_features
                ADD COLUMN IF NOT EXISTS description_language_match BOOLEAN,
                ADD COLUMN IF NOT EXISTS source_count_signal INTEGER
        """
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)

    def ensure_entity_resolution_predictions_table(self) -> None:
        query = """
            CREATE TABLE IF NOT EXISTS ml.entity_resolution_predictions (
                prediction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                pair_id UUID NOT NULL
                    REFERENCES ml.entity_candidate_pairs (pair_id)
                    ON DELETE CASCADE,
                model_name TEXT NOT NULL,
                model_version TEXT NOT NULL,
                same_game_probability NUMERIC(8, 6) NOT NULL,
                decision TEXT NOT NULL,
                threshold_policy_json JSONB NOT NULL DEFAULT '{}'::JSONB,
                explanation_factors_json JSONB NOT NULL DEFAULT '{}'::JSONB,
                predicted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (pair_id, model_name, model_version)
            )
        """
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)

    def ensure_igdb_search_results_table(self) -> None:
        query = """
            CREATE TABLE IF NOT EXISTS raw.igdb_search_results (
                id BIGSERIAL PRIMARY KEY,
                request_id UUID REFERENCES meta.api_request_log (request_id),
                source TEXT NOT NULL DEFAULT 'igdb',
                endpoint TEXT NOT NULL,
                request_hash TEXT,
                source_record_id TEXT,
                response_json JSONB NOT NULL DEFAULT '{}'::JSONB,
                response_hash TEXT,
                response_storage_path TEXT,
                loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                from_cache BOOLEAN NOT NULL DEFAULT FALSE,
                http_status INTEGER,
                error_message TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS uq_igdb_search_results_request_record
                ON raw.igdb_search_results (source, endpoint, request_hash, source_record_id);
            CREATE INDEX IF NOT EXISTS ix_igdb_search_results_source_record_id
                ON raw.igdb_search_results (source, source_record_id);
        """
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)

    def ensure_igdb_search_candidates_table(self) -> None:
        query = """
            CREATE TABLE IF NOT EXISTS ml.igdb_search_candidates (
                candidate_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                source_name TEXT NOT NULL,
                source_game_id TEXT NOT NULL,
                candidate_source TEXT NOT NULL DEFAULT 'igdb',
                igdb_id TEXT NOT NULL,
                search_rank INTEGER NOT NULL,
                query_text TEXT NOT NULL,
                query_strategy TEXT NOT NULL,
                confidence NUMERIC(5, 4),
                metadata_json JSONB NOT NULL DEFAULT '{}'::JSONB,
                retrieved_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE UNIQUE INDEX IF NOT EXISTS uq_igdb_search_candidates_match
                ON ml.igdb_search_candidates (
                    source_name,
                    source_game_id,
                    candidate_source,
                    igdb_id
                );
        """
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)

    def upsert_entity_resolution_features(
        self,
        *,
        pair_id: str,
        name_similarity: float | None,
        alias_similarity: float | None,
        release_year_diff: int | None,
        external_id_exact_match: bool | None,
        developer_overlap: float | None,
        publisher_overlap: float | None,
        platform_jaccard: float | None,
        genre_jaccard: float | None,
        tag_jaccard: float | None,
        description_available_flag: bool,
        description_language_match: bool | None,
        source_count_signal: int | None,
        features_json: Mapping[str, object],
    ) -> None:
        from psycopg.types.json import Jsonb

        self.ensure_entity_resolution_feature_columns()
        query = """
            INSERT INTO ml.entity_resolution_features (
                pair_id,
                name_similarity,
                alias_similarity,
                release_year_diff,
                external_id_exact_match,
                developer_overlap,
                publisher_overlap,
                platform_jaccard,
                genre_jaccard,
                tag_jaccard,
                description_available_flag,
                description_language_match,
                source_count_signal,
                features_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (pair_id)
            DO UPDATE
            SET name_similarity = EXCLUDED.name_similarity,
                alias_similarity = EXCLUDED.alias_similarity,
                release_year_diff = EXCLUDED.release_year_diff,
                external_id_exact_match = EXCLUDED.external_id_exact_match,
                developer_overlap = EXCLUDED.developer_overlap,
                publisher_overlap = EXCLUDED.publisher_overlap,
                platform_jaccard = EXCLUDED.platform_jaccard,
                genre_jaccard = EXCLUDED.genre_jaccard,
                tag_jaccard = EXCLUDED.tag_jaccard,
                description_available_flag = EXCLUDED.description_available_flag,
                description_language_match = EXCLUDED.description_language_match,
                source_count_signal = EXCLUDED.source_count_signal,
                features_json = EXCLUDED.features_json
        """
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        pair_id,
                        name_similarity,
                        alias_similarity,
                        release_year_diff,
                        external_id_exact_match,
                        developer_overlap,
                        publisher_overlap,
                        platform_jaccard,
                        genre_jaccard,
                        tag_jaccard,
                        description_available_flag,
                        description_language_match,
                        source_count_signal,
                        Jsonb(dict(features_json)),
                    ),
                )

    def upsert_igdb_search_candidate(
        self,
        *,
        source_name: str,
        source_game_id: str,
        candidate_source: str,
        igdb_id: str,
        search_rank: int,
        query_text: str,
        query_strategy: str,
        confidence: float | None,
        metadata_json: Mapping[str, object],
    ) -> None:
        from psycopg.types.json import Jsonb

        self.ensure_igdb_search_candidates_table()
        query = """
            INSERT INTO ml.igdb_search_candidates (
                source_name,
                source_game_id,
                candidate_source,
                igdb_id,
                search_rank,
                query_text,
                query_strategy,
                confidence,
                metadata_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_name, source_game_id, candidate_source, igdb_id)
            DO UPDATE
            SET search_rank = LEAST(ml.igdb_search_candidates.search_rank, EXCLUDED.search_rank),
                query_text = CASE
                    WHEN EXCLUDED.search_rank <= ml.igdb_search_candidates.search_rank
                        THEN EXCLUDED.query_text
                    ELSE ml.igdb_search_candidates.query_text
                END,
                query_strategy = CASE
                    WHEN EXCLUDED.search_rank <= ml.igdb_search_candidates.search_rank
                        THEN EXCLUDED.query_strategy
                    ELSE ml.igdb_search_candidates.query_strategy
                END,
                confidence = GREATEST(
                    COALESCE(ml.igdb_search_candidates.confidence, 0),
                    COALESCE(EXCLUDED.confidence, 0)
                ),
                metadata_json = EXCLUDED.metadata_json,
                retrieved_at = NOW()
        """
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        source_name,
                        source_game_id,
                        candidate_source,
                        igdb_id,
                        search_rank,
                        query_text,
                        query_strategy,
                        confidence,
                        Jsonb(dict(metadata_json)),
                    ),
                )

    def fetch_igdb_search_candidates(
        self,
        *,
        source_name: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_igdb_search_candidates_table()
        clauses = [sql.SQL("1 = 1")]
        params: list[object] = []
        if source_name is not None:
            clauses.append(sql.SQL("source_name = %s"))
            params.append(source_name)
        query = sql.SQL(
            """
            SELECT *
            FROM ml.igdb_search_candidates
            WHERE {where_clause}
            ORDER BY source_name ASC, source_game_id ASC, search_rank ASC, retrieved_at ASC
            """
        ).format(where_clause=sql.SQL(" AND ").join(clauses))
        if limit is not None:
            query += sql.SQL(" LIMIT %s")
            params.append(limit)
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return list(cursor.fetchall())

    def delete_igdb_search_candidates(self, *, source_name: str | None = None) -> None:
        self.ensure_igdb_search_candidates_table()
        query = "DELETE FROM ml.igdb_search_candidates"
        params: tuple[object, ...] = ()
        if source_name is not None:
            query += " WHERE source_name = %s"
            params = (source_name,)
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)

    def fetch_entity_resolution_features(
        self,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT *
            FROM ml.entity_resolution_features
            ORDER BY created_at ASC, pair_id ASC
        """
        params: tuple[object, ...] = ()
        if limit is not None:
            query += " LIMIT %s"
            params = (limit,)
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return list(cursor.fetchall())

    def delete_entity_resolution_predictions(self, *, model_name: str | None = None) -> None:
        query = "DELETE FROM ml.entity_resolution_predictions"
        params: tuple[object, ...] = ()
        if model_name is not None:
            query += " WHERE model_name = %s"
            params = (model_name,)
        self.ensure_entity_resolution_predictions_table()
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)

    def upsert_entity_resolution_prediction(
        self,
        *,
        pair_id: str,
        model_name: str,
        model_version: str,
        same_game_probability: float,
        decision: str,
        threshold_policy_json: Mapping[str, object],
        explanation_factors_json: Mapping[str, object],
    ) -> None:
        from psycopg.types.json import Jsonb

        self.ensure_entity_resolution_predictions_table()
        query = """
            INSERT INTO ml.entity_resolution_predictions (
                pair_id,
                model_name,
                model_version,
                same_game_probability,
                decision,
                threshold_policy_json,
                explanation_factors_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (pair_id, model_name, model_version)
            DO UPDATE
            SET same_game_probability = EXCLUDED.same_game_probability,
                decision = EXCLUDED.decision,
                threshold_policy_json = EXCLUDED.threshold_policy_json,
                explanation_factors_json = EXCLUDED.explanation_factors_json,
                predicted_at = NOW()
        """
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        pair_id,
                        model_name,
                        model_version,
                        same_game_probability,
                        decision,
                        Jsonb(dict(threshold_policy_json)),
                        Jsonb(dict(explanation_factors_json)),
                    ),
                )

    def upsert_entity_resolution_predictions(
        self,
        rows: list[Mapping[str, object]],
    ) -> None:
        from psycopg.types.json import Jsonb

        if not rows:
            return
        self.ensure_entity_resolution_predictions_table()
        query = """
            INSERT INTO ml.entity_resolution_predictions (
                pair_id,
                model_name,
                model_version,
                same_game_probability,
                decision,
                threshold_policy_json,
                explanation_factors_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (pair_id, model_name, model_version)
            DO UPDATE
            SET same_game_probability = EXCLUDED.same_game_probability,
                decision = EXCLUDED.decision,
                threshold_policy_json = EXCLUDED.threshold_policy_json,
                explanation_factors_json = EXCLUDED.explanation_factors_json,
                predicted_at = NOW()
        """
        params = [
            (
                str(row["pair_id"]),
                str(row["model_name"]),
                str(row["model_version"]),
                float(row["same_game_probability"]),
                str(row["decision"]),
                Jsonb(dict(row.get("threshold_policy_json") or {})),
                Jsonb(dict(row.get("explanation_factors_json") or {})),
            )
            for row in rows
        ]
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(query, params)

    def fetch_entity_resolution_predictions(
        self,
        *,
        model_name: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_entity_resolution_predictions_table()
        clauses = ["1 = 1"]
        params: list[object] = []
        if model_name is not None:
            clauses.append("model_name = %s")
            params.append(model_name)
        query = f"""
            SELECT *
            FROM ml.entity_resolution_predictions
            WHERE {" AND ".join(clauses)}
            ORDER BY predicted_at DESC, prediction_id ASC
        """
        if limit is not None:
            query += " LIMIT %s"
            params.append(limit)
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
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
                    [
                        tuple(_adapt_staging_value(row[column]) for column in columns)
                        for row in rows
                    ],
                )
