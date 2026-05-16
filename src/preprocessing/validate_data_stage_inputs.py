"""Validate that required stage inputs are present before ML-ready prep runs."""

from __future__ import annotations

from dataclasses import dataclass

from src.ingestion.repository import IngestionRepository

REQUIRED_STAGE_TABLES = (
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
class StageInputValidation:
    missing_tables: list[str]
    missing_sources: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing_tables and not self.missing_sources


def validate_stage_inputs(repository: IngestionRepository) -> StageInputValidation:
    existing_tables = repository.fetch_existing_tables(schemas=["stg", "ml"])
    missing_tables = [
        table_name
        for table_name in REQUIRED_STAGE_TABLES
        if tuple(table_name.split(".", maxsplit=1)) not in existing_tables
    ]
    missing_sources: list[str] = []
    if not missing_tables:
        if repository.count_rows("stg.source_games", source="rawg") == 0:
            missing_sources.append("rawg staging data")
        if repository.count_rows("stg.source_games", source="wikidata") == 0:
            missing_sources.append("wikidata staging data")
    return StageInputValidation(
        missing_tables=missing_tables,
        missing_sources=missing_sources,
    )


def validation_error_message(validation: StageInputValidation) -> str:
    parts: list[str] = []
    if validation.missing_tables:
        parts.append("missing tables: " + ", ".join(validation.missing_tables))
    if validation.missing_sources:
        parts.append("missing staged source data: " + ", ".join(validation.missing_sources))
    follow_up = (
        "Run previous stages first. Expected prerequisites: "
        "`make rawg-demo` and `make wikidata-demo` after the RAWG/Wikidata ingestion stages."
    )
    return "; ".join(parts + [follow_up])


def ensure_stage_inputs(repository: IngestionRepository) -> None:
    validation = validate_stage_inputs(repository)
    if not validation.ok:
        raise RuntimeError(validation_error_message(validation))


def main() -> int:
    repository = IngestionRepository()
    validation = validate_stage_inputs(repository)
    if validation.ok:
        print("Stage input validation passed.")
        return 0
    print(validation_error_message(validation))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
