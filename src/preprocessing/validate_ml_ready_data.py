"""Validate final data-stage prerequisites for ML-ready dataset exports."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.entity_resolution.corpus import load_source_records
from src.ingestion.repository import IngestionRepository
from src.preprocessing.data_quality import compute_data_quality_metrics
from src.utils.config import load_yaml_config, project_root

REQUIRED_SCHEMAS = ("raw", "stg", "ml", "dm", "meta")
REQUIRED_TABLES = (
    "stg.source_games",
    "stg.source_game_aliases",
    "stg.source_game_external_ids",
    "stg.source_game_genres",
    "stg.source_game_tags",
    "stg.source_game_platforms",
    "stg.source_game_companies",
    "stg.source_game_descriptions",
    "stg.source_game_ratings",
    "stg.source_game_popularity",
    "ml.entity_candidate_pairs",
    "ml.entity_resolution_features",
)
FOLLOW_UP_COMMANDS = (
    "make rawg-demo",
    "make wikidata-demo",
    "make match-external-ids",
    "make staging",
    "make dq",
)
OPTIONAL_FOLLOW_UP_COMMANDS = ("make steam-demo", "make wikipedia-demo")


@dataclass(slots=True)
class MLReadyValidation:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    checked_paths: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def _resolve_paths(
    *,
    output_dir: str | None = None,
    reports_dir: str | None = None,
    manifests_dir: str | None = None,
) -> dict[str, Path]:
    settings = load_yaml_config("data_stage").get("data_stage", {})
    config_paths = settings.get("paths", {})
    root = project_root()
    return {
        "processed_dir": root
        / str(output_dir or config_paths.get("processed_dir", "data/processed")),
        "reports_dir": root
        / str(reports_dir or config_paths.get("reports_dir", "data/artifacts/reports")),
        "manifests_dir": root
        / str(manifests_dir or config_paths.get("manifests_dir", "data/artifacts/manifests")),
    }


def _require_writable(path: Path, *, dry_run: bool, errors: list[str]) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        if dry_run:
            return
        probe = path / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        errors.append(f"directory not writable: {path} ({exc})")


def validation_error_message(validation: MLReadyValidation) -> str:
    parts = list(validation.errors)
    if validation.warnings:
        parts.append("warnings: " + "; ".join(validation.warnings))
    parts.append("Required previous commands: " + ", ".join(FOLLOW_UP_COMMANDS))
    parts.append("Optional enrichment commands: " + ", ".join(OPTIONAL_FOLLOW_UP_COMMANDS))
    return " | ".join(parts)


def validate_ml_ready_state(
    repository: IngestionRepository,
    *,
    allow_empty: bool = False,
    allow_missing_artifacts: bool = False,
    strict: bool = False,
    dry_run: bool = False,
    output_dir: str | None = None,
    reports_dir: str | None = None,
    manifests_dir: str | None = None,
) -> MLReadyValidation:
    validation = MLReadyValidation()
    existing_tables = repository.fetch_existing_tables(schemas=list(REQUIRED_SCHEMAS))
    existing_schemas = {schema for schema, _ in existing_tables}

    for schema_name in REQUIRED_SCHEMAS:
        if schema_name not in existing_schemas:
            validation.errors.append(f"missing schema: {schema_name}")

    for table_name in REQUIRED_TABLES:
        if tuple(table_name.split(".", maxsplit=1)) not in existing_tables:
            validation.errors.append(f"missing table: {table_name}")

    paths = _resolve_paths(
        output_dir=output_dir,
        reports_dir=reports_dir,
        manifests_dir=manifests_dir,
    )
    validation.checked_paths = {key: str(value) for key, value in paths.items()}
    for path in paths.values():
        _require_writable(path, dry_run=dry_run, errors=validation.errors)

    if validation.errors and not allow_empty:
        return validation

    required_sources = ("rawg", "wikidata")
    optional_sources = ("steam", "wikipedia", "igdb")
    for source_name in (*required_sources, *optional_sources):
        count = repository.count_rows("stg.source_games", source=source_name)
        validation.counts[f"{source_name}_game_count"] = count
        if source_name in required_sources and count == 0 and not allow_empty:
            validation.errors.append(f"missing required staging rows for source: {source_name}")
        if source_name in optional_sources and count == 0:
            validation.warnings.append(f"optional source not loaded: {source_name}")

    rawg_rows = repository.fetch_staging_rows("stg.source_games", source="rawg")
    rawg_slug_count = sum(1 for row in rawg_rows if row.get("slug") not in (None, ""))
    wikidata_external_id_count = repository.count_rows(
        "stg.source_game_external_ids",
        source="wikidata",
    )
    validation.counts["rawg_slug_count"] = rawg_slug_count
    validation.counts["wikidata_external_id_count"] = wikidata_external_id_count
    if validation.counts["rawg_game_count"] > 0 and rawg_slug_count == 0 and not allow_empty:
        validation.errors.append("missing RAWG slugs for source: rawg")
    if (
        validation.counts["wikidata_game_count"] > 0
        and wikidata_external_id_count == 0
        and not allow_empty
    ):
        validation.errors.append("missing external IDs for source: wikidata")

    candidate_pair_count = repository.count_rows("ml.entity_candidate_pairs")
    feature_count = repository.count_rows("ml.entity_resolution_features")
    validation.counts["candidate_pair_count"] = candidate_pair_count
    validation.counts["feature_base_count"] = feature_count
    if candidate_pair_count == 0 and not allow_empty and not allow_missing_artifacts:
        validation.errors.append("candidate pairs missing")
    if feature_count == 0 and not allow_empty and not allow_missing_artifacts:
        validation.errors.append("feature base missing")

    deterministic_positive_count = len(
        [
            pair
            for pair in repository.fetch_candidate_pairs()
            if str(pair.get("label_value") or "") == "1"
        ]
    )
    validation.counts["deterministic_positive_count"] = deterministic_positive_count
    if (
        validation.counts["rawg_game_count"] > 0
        and validation.counts["wikidata_game_count"] > 0
        and deterministic_positive_count == 0
        and not allow_empty
    ):
        validation.errors.append("deterministic matches missing")

    try:
        records = load_source_records(repository)
        summary = compute_data_quality_metrics(
            records,
            repository.fetch_candidate_pairs(),
            source_game_rows=repository.fetch_staging_rows("stg.source_games"),
            alias_rows=repository.fetch_staging_rows("stg.source_game_aliases"),
            description_rows=repository.fetch_staging_rows("stg.source_game_descriptions"),
            rating_rows=repository.fetch_staging_rows("stg.source_game_ratings"),
            popularity_rows=repository.fetch_staging_rows("stg.source_game_popularity"),
            url_rows=repository.fetch_staging_rows("stg.source_game_urls"),
        )
        validation.counts["record_count_total"] = sum(summary["record_count_by_source"].values())
    except Exception as exc:  # pragma: no cover - defensive runtime path
        validation.errors.append(f"DQ metrics unavailable: {exc}")

    if strict and validation.warnings:
        validation.errors.extend(f"strict warning: {warning}" for warning in validation.warnings)

    return validation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate ML-ready data-stage prerequisites.")
    parser.add_argument("--allow-empty", action="store_true", help="Allow empty datasets.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate without writing artifacts.",
    )
    parser.add_argument("--output-dir", help="Override processed output directory.")
    parser.add_argument("--reports-dir", help="Override reports output directory.")
    parser.add_argument("--manifests-dir", help="Override manifests output directory.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository = IngestionRepository()
    validation = validate_ml_ready_state(
        repository,
        allow_empty=args.allow_empty,
        strict=args.strict,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
        reports_dir=args.reports_dir,
        manifests_dir=args.manifests_dir,
    )
    payload: dict[str, Any] = {
        "allow_empty": args.allow_empty,
        "strict": args.strict,
        "dry_run": args.dry_run,
        "ok": validation.ok,
        "errors": validation.errors,
        "warnings": validation.warnings,
        "counts": validation.counts,
        "paths": validation.checked_paths,
    }
    print(payload)
    if validation.ok:
        return 0
    print(validation_error_message(validation))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
