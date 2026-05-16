"""Validate current staging state before DQ and analysis steps."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from src.ingestion.repository import IngestionRepository

REQUIRED_SCHEMAS = ("stg", "ml")
REQUIRED_TABLES = (
    "stg.source_games",
    "stg.source_game_aliases",
    "stg.source_game_external_ids",
    "stg.source_game_genres",
    "stg.source_game_platforms",
    "stg.source_game_companies",
    "stg.source_game_descriptions",
    "stg.source_game_ratings",
    "ml.entity_candidate_pairs",
    "ml.entity_resolution_features",
)


@dataclass(frozen=True, slots=True)
class StagingStateValidation:
    missing_schemas: list[str]
    missing_tables: list[str]
    empty_tables: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing_schemas and not self.missing_tables and not self.empty_tables


def validate_staging_state(
    repository: IngestionRepository,
    *,
    allow_empty: bool = False,
) -> StagingStateValidation:
    existing_tables = repository.fetch_existing_tables(schemas=list(REQUIRED_SCHEMAS))
    existing_schemas = {schema for schema, _ in existing_tables}
    missing_schemas = [schema for schema in REQUIRED_SCHEMAS if schema not in existing_schemas]
    missing_tables = [
        table_name
        for table_name in REQUIRED_TABLES
        if tuple(table_name.split(".", maxsplit=1)) not in existing_tables
    ]
    empty_tables: list[str] = []
    if not allow_empty and not missing_tables:
        emptiness_checks = {
            "stg.source_games (rawg)": ("stg.source_games", "rawg"),
            "stg.source_games (wikidata)": ("stg.source_games", "wikidata"),
            "stg.source_game_external_ids": ("stg.source_game_external_ids", None),
            "ml.entity_candidate_pairs": ("ml.entity_candidate_pairs", None),
            "ml.entity_resolution_features": ("ml.entity_resolution_features", None),
        }
        for label, (table_name, source) in emptiness_checks.items():
            if repository.count_rows(table_name, source=source) == 0:
                empty_tables.append(label)
    return StagingStateValidation(missing_schemas, missing_tables, empty_tables)


def validation_error_message(validation: StagingStateValidation) -> str:
    parts: list[str] = []
    if validation.missing_schemas:
        parts.append("missing schemas: " + ", ".join(validation.missing_schemas))
    if validation.missing_tables:
        parts.append("missing tables: " + ", ".join(validation.missing_tables))
    if validation.empty_tables:
        parts.append("empty required inputs: " + ", ".join(validation.empty_tables))
    follow_up = (
        "Run prerequisites first: `make rawg-demo`, `make wikidata-demo`, "
        "then `make entity-data-base`."
    )
    return "; ".join(parts + [follow_up])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate staging schemas, tables, and row presence."
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Validate schemas and tables only, without requiring row presence.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository = IngestionRepository()
    validation = validate_staging_state(repository, allow_empty=args.allow_empty)
    if validation.ok:
        print("Staging state validation passed.")
        return 0
    print(validation_error_message(validation))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
