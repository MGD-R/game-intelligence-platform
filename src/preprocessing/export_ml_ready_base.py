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
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
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


def _normalized_type_family(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    return "other"


def _normalize_rows_without_schema(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized_rows = [{key: _normalize_value(value) for key, value in row.items()} for row in rows]
    keys = sorted({key for row in normalized_rows for key in row})
    heterogeneous_keys: set[str] = set()
    for key in keys:
        families = {
            family
            for row in normalized_rows
            if (family := _normalized_type_family(row.get(key))) is not None
        }
        if len(families) > 1:
            heterogeneous_keys.add(key)
    if not heterogeneous_keys:
        return normalized_rows
    for row in normalized_rows:
        for key in keys:
            row.setdefault(key, None)
        for key in heterogeneous_keys:
            value = row.get(key)
            if value is not None:
                row[key] = str(value)
    return normalized_rows


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
            normalized_rows = _normalize_rows_without_schema(rows)
        if schema:
            frame = pl.DataFrame(normalized_rows, schema=schema)
        else:
            frame = pl.DataFrame(normalized_rows, infer_schema_length=None)
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
