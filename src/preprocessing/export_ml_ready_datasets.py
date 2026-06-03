"""Export final ML-ready and analysis-ready parquet snapshots."""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

from src.entity_resolution.build_manual_review_seed import build_manual_review_rows
from src.entity_resolution.corpus import load_source_records
from src.ingestion.repository import IngestionRepository
from src.preprocessing.export_ml_ready_base import write_parquet
from src.preprocessing.validate_ml_ready_data import (
    validate_ml_ready_state,
    validation_error_message,
)
from src.utils.config import project_root

DATASET_SPECS: dict[str, dict[str, object]] = {
    "source_games": {
        "table": "stg.source_games",
        "required": True,
        "schema": {
            "source": pl.Utf8,
            "source_game_id": pl.Utf8,
            "name": pl.Utf8,
            "name_normalized": pl.Utf8,
            "release_date": pl.Utf8,
            "release_year": pl.Int64,
        },
    },
    "source_aliases": {
        "table": "stg.source_game_aliases",
        "required": False,
        "schema": {
            "source": pl.Utf8,
            "source_game_id": pl.Utf8,
            "alias": pl.Utf8,
            "language": pl.Utf8,
        },
    },
    "source_external_ids": {
        "table": "stg.source_game_external_ids",
        "required": True,
        "schema": {
            "source": pl.Utf8,
            "source_game_id": pl.Utf8,
            "external_source": pl.Utf8,
            "external_id": pl.Utf8,
        },
    },
    "source_genres": {
        "table": "stg.source_game_genres",
        "required": True,
        "schema": {
            "source": pl.Utf8,
            "source_game_id": pl.Utf8,
            "genre_name": pl.Utf8,
        },
    },
    "source_tags": {
        "table": "stg.source_game_tags",
        "required": False,
        "schema": {
            "source": pl.Utf8,
            "source_game_id": pl.Utf8,
            "tag_name": pl.Utf8,
        },
    },
    "source_platforms": {
        "table": "stg.source_game_platforms",
        "required": True,
        "schema": {
            "source": pl.Utf8,
            "source_game_id": pl.Utf8,
            "platform_name": pl.Utf8,
        },
    },
    "source_companies": {
        "table": "stg.source_game_companies",
        "required": False,
        "schema": {
            "source": pl.Utf8,
            "source_game_id": pl.Utf8,
            "company_name": pl.Utf8,
            "company_role": pl.Utf8,
        },
    },
    "source_descriptions": {
        "table": "stg.source_game_descriptions",
        "required": False,
        "schema": {
            "source": pl.Utf8,
            "source_game_id": pl.Utf8,
            "description_type": pl.Utf8,
            "language": pl.Utf8,
            "description_text": pl.Utf8,
        },
    },
    "source_ratings": {
        "table": "stg.source_game_ratings",
        "required": True,
        "schema": {
            "source": pl.Utf8,
            "source_game_id": pl.Utf8,
            "rating_type": pl.Utf8,
            "rating_value": pl.Float64,
        },
    },
    "source_popularity": {
        "table": "stg.source_game_popularity",
        "required": False,
        "schema": {
            "source": pl.Utf8,
            "source_game_id": pl.Utf8,
            "metric_name": pl.Utf8,
            "metric_value": pl.Float64,
        },
    },
    "entity_candidate_pairs": {
        "table": "ml.entity_candidate_pairs",
        "required": True,
        "schema": {
            "pair_id": pl.Utf8,
            "source_a": pl.Utf8,
            "source_id_a": pl.Utf8,
            "source_b": pl.Utf8,
            "source_id_b": pl.Utf8,
            "candidate_source": pl.Utf8,
            "label_source": pl.Utf8,
            "label_value": pl.Utf8,
            "confidence": pl.Float64,
        },
    },
    "entity_resolution_feature_base": {
        "table": "ml.entity_resolution_features",
        "required": True,
        "schema": {
            "pair_id": pl.Utf8,
            "name_similarity": pl.Float64,
            "alias_similarity": pl.Float64,
            "release_year_diff": pl.Int64,
            "external_id_exact_match": pl.Boolean,
            "developer_overlap": pl.Float64,
            "publisher_overlap": pl.Float64,
            "platform_jaccard": pl.Float64,
            "genre_jaccard": pl.Float64,
            "tag_jaccard": pl.Float64,
            "description_available_flag": pl.Boolean,
            "description_language_match": pl.Boolean,
            "source_count_signal": pl.Int64,
            "features_json": pl.Utf8,
        },
    },
    "canonical_games": {
        "table": "dm.canonical_games",
        "required": True,
        "schema": {
            "canonical_game_id": pl.Utf8,
            "canonical_name": pl.Utf8,
            "release_year": pl.Int64,
        },
    },
    "canonical_game_sources": {
        "table": "dm.canonical_game_sources",
        "required": True,
        "schema": {
            "canonical_game_id": pl.Utf8,
            "source": pl.Utf8,
            "source_game_id": pl.Utf8,
            "linkage_confidence": pl.Float64,
        },
    },
    "canonical_game_aliases": {
        "table": "dm.canonical_game_aliases",
        "required": False,
        "schema": {
            "canonical_game_id": pl.Utf8,
            "alias": pl.Utf8,
            "language": pl.Utf8,
        },
    },
    "canonical_game_external_ids": {
        "table": "dm.canonical_game_external_ids",
        "required": False,
        "schema": {
            "canonical_game_id": pl.Utf8,
            "external_source": pl.Utf8,
            "external_id": pl.Utf8,
        },
    },
    "game_recommendations": {
        "table": "dm.game_recommendations",
        "required": False,
        "schema": {
            "canonical_game_id": pl.Utf8,
            "recommended_canonical_game_id": pl.Utf8,
            "rank": pl.Int64,
            "score": pl.Float64,
            "algorithm": pl.Utf8,
            "explanation_factors_json": pl.Utf8,
        },
    },
    "manual_review_seed": {
        "table": None,
        "required": False,
        "schema": {
            "pair_id": pl.Utf8,
            "review_category": pl.Utf8,
            "source_a": pl.Utf8,
            "source_id_a": pl.Utf8,
            "name_a": pl.Utf8,
            "release_year_a": pl.Int64,
            "source_b": pl.Utf8,
            "source_id_b": pl.Utf8,
            "name_b": pl.Utf8,
            "release_year_b": pl.Int64,
            "candidate_source": pl.Utf8,
            "label_source": pl.Utf8,
            "label_value": pl.Utf8,
            "confidence": pl.Float64,
            "name_similarity": pl.Float64,
            "alias_similarity": pl.Float64,
            "release_year_diff": pl.Int64,
            "external_id_exact_match": pl.Boolean,
            "description_available_flag": pl.Boolean,
            "description_language_match": pl.Boolean,
            "source_count_signal": pl.Int64,
            "features_json": pl.Utf8,
        },
    },
}


def build_output_paths(output_dir: Path) -> dict[str, Path]:
    return {name: output_dir / f"{name}.parquet" for name in DATASET_SPECS}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export final ML-ready datasets to parquet.")
    parser.add_argument("--output-dir", default=str(project_root() / "data" / "processed"))
    parser.add_argument("--allow-empty", action="store_true", help="Allow empty output datasets.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview export paths without writes.",
    )
    parser.add_argument("--limit", type=int, help="Optional row limit per dataset.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = Path(args.output_dir)
    output_paths = build_output_paths(output_dir)
    if args.dry_run:
        print({key: str(path) for key, path in output_paths.items()})
        return 0

    repository = IngestionRepository()
    validation = validate_ml_ready_state(
        repository,
        allow_empty=args.allow_empty,
        output_dir=str(output_dir),
    )
    if not validation.ok:
        raise RuntimeError(validation_error_message(validation))

    records = load_source_records(repository)
    candidate_pairs = repository.fetch_candidate_pairs(limit=args.limit)
    feature_rows = repository.fetch_entity_resolution_features(limit=args.limit)
    feature_by_pair_id = {str(row["pair_id"]): row for row in feature_rows}
    manual_review_rows = build_manual_review_rows(records, candidate_pairs, feature_by_pair_id)

    for dataset_name, spec in DATASET_SPECS.items():
        rows: list[dict[str, object]]
        if dataset_name == "manual_review_seed":
            rows = manual_review_rows
        else:
            table_name = str(spec["table"])
            if table_name.startswith("stg."):
                rows = repository.fetch_staging_rows(table_name, limit=args.limit)
            elif table_name.startswith("dm."):
                rows = repository.fetch_staging_rows(table_name, limit=args.limit)
            elif table_name == "ml.entity_candidate_pairs":
                rows = candidate_pairs
            else:
                rows = feature_rows

        if not rows and bool(spec["required"]) and not args.allow_empty:
            raise RuntimeError(f"Required dataset is empty: {dataset_name}")
        write_parquet(output_paths[dataset_name], rows, schema=spec["schema"])

    print({key: str(path) for key, path in output_paths.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
