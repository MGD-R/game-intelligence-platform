from __future__ import annotations

from pathlib import Path

from src.database.check_schema import (
    EXPECTED_SCHEMAS,
    EXPECTED_TABLES,
    expected_table_count,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def read_file(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_sql_layer_files_exist() -> None:
    required_files = [
        "sql/meta/create_meta_tables.sql",
        "sql/raw/create_raw_tables.sql",
        "sql/stg/create_stg_tables.sql",
        "sql/ml/create_ml_tables.sql",
        "sql/dm/create_dm_tables.sql",
        "docker/postgres/init/001_create_schemas.sql",
        "docker/postgres/init/002_create_extensions.sql",
        "docker/postgres/init/003_create_meta_tables.sql",
        "docker/postgres/init/004_create_raw_tables.sql",
        "docker/postgres/init/005_create_stg_tables.sql",
        "docker/postgres/init/006_create_ml_tables.sql",
        "docker/postgres/init/007_create_dm_tables.sql",
    ]

    for relative_path in required_files:
        assert (REPO_ROOT / relative_path).exists(), relative_path


def test_schema_init_scripts_cover_required_schemas_and_extensions() -> None:
    schema_sql = read_file("docker/postgres/init/001_create_schemas.sql")
    extension_sql = read_file("docker/postgres/init/002_create_extensions.sql")

    for schema_name in EXPECTED_SCHEMAS:
        assert f"CREATE SCHEMA IF NOT EXISTS {schema_name};" in schema_sql

    for extension_name in ("pg_trgm", "unaccent", '"uuid-ossp"'):
        assert f"CREATE EXTENSION IF NOT EXISTS {extension_name};" in extension_sql


def test_sql_files_cover_expected_tables() -> None:
    sql_by_schema = {
        "meta": read_file("sql/meta/create_meta_tables.sql"),
        "raw": read_file("sql/raw/create_raw_tables.sql"),
        "stg": read_file("sql/stg/create_stg_tables.sql"),
        "ml": read_file("sql/ml/create_ml_tables.sql"),
        "dm": read_file("sql/dm/create_dm_tables.sql"),
    }

    for schema_name, table_names in EXPECTED_TABLES.items():
        sql_text = sql_by_schema[schema_name]
        for table_name in table_names:
            assert f"CREATE TABLE IF NOT EXISTS {schema_name}.{table_name}" in sql_text


def test_schema_checker_metadata_is_stable() -> None:
    assert expected_table_count() == 31
    assert "source_games" in EXPECTED_TABLES["stg"]
    ml_sql = read_file("sql/ml/create_ml_tables.sql")
    assert "CREATE TABLE IF NOT EXISTS ml.entity_resolution_predictions" in ml_sql
