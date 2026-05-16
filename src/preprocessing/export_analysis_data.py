"""Export analysis-ready staging and ER snapshots to parquet."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.ingestion.repository import IngestionRepository
from src.preprocessing.export_ml_ready_base import write_parquet
from src.preprocessing.validate_staging_state import (
    validate_staging_state,
    validation_error_message,
)
from src.utils.config import project_root


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export analysis-ready staging and ER data.")
    parser.add_argument("--output-dir", default=str(project_root() / "data" / "processed"))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview export paths without DB reads or writes.",
    )
    parser.add_argument("--limit", type=int, help="Optional export row limit per dataset.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = Path(args.output_dir)
    outputs = {
        "source_games": output_dir / "source_games.parquet",
        "source_aliases": output_dir / "source_aliases.parquet",
        "source_external_ids": output_dir / "source_external_ids.parquet",
        "source_genres": output_dir / "source_genres.parquet",
        "source_tags": output_dir / "source_tags.parquet",
        "source_platforms": output_dir / "source_platforms.parquet",
        "source_companies": output_dir / "source_companies.parquet",
        "source_descriptions": output_dir / "source_descriptions.parquet",
        "source_ratings": output_dir / "source_ratings.parquet",
        "source_popularity": output_dir / "source_popularity.parquet",
        "entity_candidate_pairs": output_dir / "entity_candidate_pairs.parquet",
        "entity_resolution_feature_base": output_dir / "entity_resolution_feature_base.parquet",
    }
    if args.dry_run:
        print({key: str(path) for key, path in outputs.items()})
        return 0

    repository = IngestionRepository()
    validation = validate_staging_state(repository)
    if not validation.ok:
        raise RuntimeError(validation_error_message(validation))
    write_parquet(
        outputs["source_games"],
        repository.fetch_staging_rows("stg.source_games", limit=args.limit),
    )
    write_parquet(
        outputs["source_aliases"],
        repository.fetch_staging_rows("stg.source_game_aliases", limit=args.limit),
    )
    write_parquet(
        outputs["source_external_ids"],
        repository.fetch_staging_rows("stg.source_game_external_ids", limit=args.limit),
    )
    write_parquet(
        outputs["source_genres"],
        repository.fetch_staging_rows("stg.source_game_genres", limit=args.limit),
    )
    write_parquet(
        outputs["source_tags"],
        repository.fetch_staging_rows("stg.source_game_tags", limit=args.limit),
    )
    write_parquet(
        outputs["source_platforms"],
        repository.fetch_staging_rows("stg.source_game_platforms", limit=args.limit),
    )
    write_parquet(
        outputs["source_companies"],
        repository.fetch_staging_rows("stg.source_game_companies", limit=args.limit),
    )
    write_parquet(
        outputs["source_descriptions"],
        repository.fetch_staging_rows("stg.source_game_descriptions", limit=args.limit),
    )
    write_parquet(
        outputs["source_ratings"],
        repository.fetch_staging_rows("stg.source_game_ratings", limit=args.limit),
    )
    write_parquet(
        outputs["source_popularity"],
        repository.fetch_staging_rows("stg.source_game_popularity", limit=args.limit),
    )
    write_parquet(
        outputs["entity_candidate_pairs"],
        repository.fetch_candidate_pairs(limit=args.limit),
    )
    write_parquet(
        outputs["entity_resolution_feature_base"],
        repository.fetch_entity_resolution_features(limit=args.limit),
    )
    print({key: str(path) for key, path in outputs.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
