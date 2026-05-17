"""Export ML-ready candidate corpus snapshots to parquet files."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import polars as pl

from src.ingestion.repository import IngestionRepository
from src.preprocessing.validate_data_stage_inputs import ensure_stage_inputs
from src.utils.config import project_root


def _normalize_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, ensure_ascii=True)
    if isinstance(value, list):
        return json.dumps(value, sort_keys=False, ensure_ascii=True)
    return value


def _normalize_value_for_dtype(value: Any, dtype: pl.DataType) -> Any:
    normalized = _normalize_value(value)
    if normalized is None:
        return None
    if dtype == pl.Utf8:
        if isinstance(normalized, (date, datetime)):
            return normalized.isoformat()
        return str(normalized)
    if dtype == pl.Float64:
        if isinstance(normalized, Decimal):
            return float(normalized)
        return float(normalized)
    if dtype == pl.Int64:
        return int(normalized)
    if dtype == pl.Boolean:
        return bool(normalized)
    return normalized


def write_parquet(
    path: Path,
    rows: list[dict[str, object]],
    *,
    schema: dict[str, pl.DataType] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        if schema:
            normalized_rows = [
                {
                    key: _normalize_value_for_dtype(row.get(key), dtype)
                    for key, dtype in schema.items()
                }
                for row in rows
            ]
        else:
            normalized_rows = [
                {key: _normalize_value(value) for key, value in row.items()} for row in rows
            ]
        frame = pl.DataFrame(normalized_rows, schema=schema)
    elif schema:
        frame = pl.DataFrame(schema=schema)
    else:
        frame = pl.DataFrame([{"status": "empty"}])
    frame.write_parquet(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export ML-ready snapshots to parquet.")
    parser.add_argument("--output-dir", default=str(project_root() / "data" / "processed"))
    parser.add_argument("--limit", type=int, help="Optional row limit per exported dataset.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview export paths without DB reads or writes.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = Path(args.output_dir)
    outputs = {
        "entity_candidate_pairs": output_dir / "entity_candidate_pairs.parquet",
        "entity_resolution_feature_base": output_dir / "entity_resolution_feature_base.parquet",
        "source_external_ids": output_dir / "source_external_ids.parquet",
        "source_aliases": output_dir / "source_aliases.parquet",
    }
    if args.dry_run:
        print({key: str(path) for key, path in outputs.items()})
        return 0

    repository = IngestionRepository()
    ensure_stage_inputs(repository)
    write_parquet(
        outputs["entity_candidate_pairs"],
        repository.fetch_candidate_pairs(limit=args.limit),
    )
    write_parquet(
        outputs["entity_resolution_feature_base"],
        repository.fetch_entity_resolution_features(limit=args.limit),
    )
    write_parquet(
        outputs["source_external_ids"],
        repository.fetch_staging_rows("stg.source_game_external_ids", limit=args.limit),
    )
    write_parquet(
        outputs["source_aliases"],
        repository.fetch_staging_rows("stg.source_game_aliases", limit=args.limit),
    )
    print({key: str(path) for key, path in outputs.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
