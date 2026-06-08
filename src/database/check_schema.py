"""Validate that the required PostgreSQL schemas and tables exist."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable

EXPECTED_SCHEMAS = ("raw", "stg", "ml", "dm", "meta")
EXPECTED_TABLES: dict[str, tuple[str, ...]] = {
    "meta": (
        "api_request_log",
        "api_quota_usage",
        "pipeline_run_log",
        "ingestion_checkpoint",
    ),
    "raw": (
        "rawg_game_index",
        "rawg_game_details",
        "rawg_reference_data",
        "wikidata_sparql_results",
        "wikidata_entities",
        "steam_app_details",
        "wikipedia_pages",
        "igdb_games",
        "igdb_reference_data",
        "igdb_search_results",
    ),
    "stg": (
        "source_games",
        "source_game_aliases",
        "source_game_external_ids",
        "source_game_genres",
        "source_game_tags",
        "source_game_themes",
        "source_game_platforms",
        "source_game_companies",
        "source_game_descriptions",
        "source_game_ratings",
        "source_game_popularity",
        "source_game_urls",
    ),
    "ml": (
        "entity_candidate_pairs",
        "entity_resolution_features",
        "igdb_search_candidates",
    ),
    "dm": (
        "canonical_games",
        "canonical_game_sources",
        "canonical_game_aliases",
        "canonical_game_external_ids",
    ),
}


def expected_table_count() -> int:
    return sum(len(tables) for tables in EXPECTED_TABLES.values())


def get_connection_settings() -> tuple[str, int]:
    dsn = os.getenv("DATABASE_URL", "postgresql://gip:change-me@postgres:5432/gip")
    timeout = int(os.getenv("DATABASE_CONNECT_TIMEOUT", "3"))
    return dsn, timeout


def fetch_existing_schema_state() -> tuple[set[str], set[tuple[str, str]]]:
    dsn, timeout = get_connection_settings()

    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - environment issue
        raise RuntimeError("psycopg is not installed") from exc

    with psycopg.connect(dsn, connect_timeout=timeout) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name = ANY(%s)
                ORDER BY schema_name
                """,
                (list(EXPECTED_SCHEMAS),),
            )
            existing_schemas = {row[0] for row in cursor.fetchall()}

            cursor.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                  AND table_schema = ANY(%s)
                ORDER BY table_schema, table_name
                """,
                (list(EXPECTED_SCHEMAS),),
            )
            existing_tables = {(row[0], row[1]) for row in cursor.fetchall()}

    return existing_schemas, existing_tables


def validate_schema_state(
    existing_schemas: set[str], existing_tables: set[tuple[str, str]]
) -> list[str]:
    errors: list[str] = []

    for schema_name in EXPECTED_SCHEMAS:
        if schema_name not in existing_schemas:
            errors.append(f"missing schema: {schema_name}")

    for schema_name, table_names in EXPECTED_TABLES.items():
        for table_name in table_names:
            if (schema_name, table_name) not in existing_tables:
                errors.append(f"missing table: {schema_name}.{table_name}")

    return errors


def format_summary(errors: Iterable[str]) -> str:
    error_list = list(errors)
    if not error_list:
        return (
            "Schema check passed: "
            f"{len(EXPECTED_SCHEMAS)} schemas and {expected_table_count()} tables present."
        )
    return "Schema check failed:\n- " + "\n- ".join(error_list)


def main() -> int:
    try:
        existing_schemas, existing_tables = fetch_existing_schema_state()
        errors = validate_schema_state(existing_schemas, existing_tables)
    except Exception as exc:  # pragma: no cover - runtime integration path
        print(f"Schema check failed: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1

    summary = format_summary(errors)
    stream = sys.stdout if not errors else sys.stderr
    print(summary, file=stream)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
