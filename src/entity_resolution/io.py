"""Shared loaders and path helpers for the baseline entity-resolution stage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from src.ingestion.repository import IngestionRepository
from src.preprocessing.export_ml_ready_base import write_parquet
from src.preprocessing.export_ml_ready_datasets import DATASET_SPECS
from src.preprocessing.validate_ml_ready_data import validate_ml_ready_state
from src.utils.config import load_yaml_config, project_root

ER_REQUIRED_COMMANDS = (
    "make rawg-demo",
    "make wikidata-demo",
    "make match-external-ids",
    "make staging",
    "make ml-ready-data",
)


@dataclass(frozen=True, slots=True)
class EntityResolutionPaths:
    candidate_pairs_path: Path
    feature_base_path: Path
    manual_review_seed_path: Path
    reports_dir: Path
    models_dir: Path
    predictions_dir: Path


def load_entity_resolution_config() -> dict[str, Any]:
    return load_yaml_config("entity_resolution").get("entity_resolution", {})


def resolve_entity_resolution_paths() -> EntityResolutionPaths:
    config = load_entity_resolution_config()
    dataset = config.get("dataset", {})
    outputs = config.get("outputs", {})
    root = project_root()
    return EntityResolutionPaths(
        candidate_pairs_path=root / str(dataset.get("candidate_pairs_path")),
        feature_base_path=root / str(dataset.get("feature_base_path")),
        manual_review_seed_path=root / str(dataset.get("manual_review_seed_path")),
        reports_dir=root / str(outputs.get("reports_dir")),
        models_dir=root / str(outputs.get("models_dir")),
        predictions_dir=root / str(outputs.get("predictions_dir")),
    )


def feature_columns() -> list[str]:
    config = load_entity_resolution_config()
    return [str(name) for name in config.get("features", {}).get("numeric", [])]


def _frame_from_rows(
    rows: list[dict[str, object]],
    dataset_name: str,
) -> pl.DataFrame:
    schema = DATASET_SPECS[dataset_name]["schema"]
    if rows:
        return pl.DataFrame(rows, schema=schema)
    return pl.DataFrame(schema=schema)


def load_candidate_pairs_frame(
    repository: IngestionRepository | None = None,
    *,
    limit: int | None = None,
) -> pl.DataFrame:
    paths = resolve_entity_resolution_paths()
    if paths.candidate_pairs_path.exists():
        frame = pl.read_parquet(paths.candidate_pairs_path)
        return frame.head(limit) if limit is not None else frame
    repository = repository or IngestionRepository()
    return _frame_from_rows(
        repository.fetch_candidate_pairs(limit=limit),
        "entity_candidate_pairs",
    )


def load_feature_base_frame(
    repository: IngestionRepository | None = None,
    *,
    limit: int | None = None,
) -> pl.DataFrame:
    paths = resolve_entity_resolution_paths()
    if paths.feature_base_path.exists():
        frame = pl.read_parquet(paths.feature_base_path)
        return frame.head(limit) if limit is not None else frame
    repository = repository or IngestionRepository()
    return _frame_from_rows(
        repository.fetch_entity_resolution_features(limit=limit),
        "entity_resolution_feature_base",
    )


def load_manual_review_seed_frame(*, limit: int | None = None) -> pl.DataFrame:
    paths = resolve_entity_resolution_paths()
    if not paths.manual_review_seed_path.exists():
        return pl.DataFrame(schema=DATASET_SPECS["manual_review_seed"]["schema"])
    frame = pl.read_parquet(paths.manual_review_seed_path)
    return frame.head(limit) if limit is not None else frame


def load_source_games_frame(
    repository: IngestionRepository | None = None,
    *,
    limit: int | None = None,
) -> pl.DataFrame:
    source_games_path = project_root() / "data" / "processed" / "source_games.parquet"
    if source_games_path.exists():
        frame = pl.read_parquet(source_games_path)
        return frame.head(limit) if limit is not None else frame
    repository = repository or IngestionRepository()
    return _frame_from_rows(
        repository.fetch_staging_rows("stg.source_games", limit=limit),
        "source_games",
    )


def ensure_er_inputs(
    *,
    allow_empty: bool = False,
    allow_missing_artifacts: bool = False,
) -> None:
    repository = IngestionRepository()
    paths = resolve_entity_resolution_paths()
    validation = validate_ml_ready_state(
        repository,
        allow_empty=allow_empty,
        allow_missing_artifacts=allow_missing_artifacts,
        output_dir=str(paths.predictions_dir.parent),
        reports_dir=str(paths.reports_dir.parent),
        manifests_dir=str(paths.reports_dir.parent.parent / "manifests"),
    )
    if not validation.ok:
        parts = list(validation.errors)
        if validation.warnings:
            parts.append("warnings: " + "; ".join(validation.warnings))
        parts.append("Required ER stage inputs: " + ", ".join(ER_REQUIRED_COMMANDS))
        raise RuntimeError(" | ".join(parts))


def ensure_output_directories() -> EntityResolutionPaths:
    paths = resolve_entity_resolution_paths()
    paths.reports_dir.mkdir(parents=True, exist_ok=True)
    paths.models_dir.mkdir(parents=True, exist_ok=True)
    paths.predictions_dir.mkdir(parents=True, exist_ok=True)
    return paths


def write_er_parquet(path: Path, rows: list[dict[str, object]], dataset_name: str) -> None:
    write_parquet(path, rows, schema=DATASET_SPECS.get(dataset_name, {}).get("schema"))
