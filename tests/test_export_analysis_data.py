from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import polars as pl

from src.preprocessing.export_ml_ready_base import (
    _normalize_rows_without_schema,
    _normalize_value,
    write_parquet,
)


def test_export_analysis_helper_writes_parquet(tmp_path: Path) -> None:
    output_path = tmp_path / "source_games.parquet"
    write_parquet(output_path, [{"source": "rawg", "source_game_id": "1"}])
    frame = pl.read_parquet(output_path)
    assert frame.height == 1


def test_normalize_value_converts_uuid_to_string() -> None:
    value = UUID("66ee85a3-6fb6-4a64-8825-c4afe35a8238")
    assert _normalize_value(value) == "66ee85a3-6fb6-4a64-8825-c4afe35a8238"


def test_normalize_value_converts_decimal_and_date_types() -> None:
    assert _normalize_value(Decimal("84.0000")) == 84.0
    assert _normalize_value(date(2017, 3, 20)) == "2017-03-20"


def test_write_parquet_respects_schema_type_conversions(tmp_path: Path) -> None:
    output_path = tmp_path / "ml_ready.parquet"
    write_parquet(
        output_path,
        [
            {
                "pair_id": UUID("66ee85a3-6fb6-4a64-8825-c4afe35a8238"),
                "release_date": date(2017, 3, 20),
                "confidence": Decimal("1.0000"),
            }
        ],
        schema={
            "pair_id": pl.Utf8,
            "release_date": pl.Utf8,
            "confidence": pl.Float64,
        },
    )
    frame = pl.read_parquet(output_path)
    assert frame.schema == {
        "pair_id": pl.String,
        "release_date": pl.String,
        "confidence": pl.Float64,
    }
    assert frame.row(0) == (
        "66ee85a3-6fb6-4a64-8825-c4afe35a8238",
        "2017-03-20",
        1.0,
    )


def test_normalize_rows_without_schema_coerces_mixed_type_columns() -> None:
    rows = _normalize_rows_without_schema(
        [
            {"source_game_id": "Q1", "rating_count": 10},
            {"source_game_id": 328, "rating_count": 20, "rating_scale": "100"},
        ]
    )

    assert rows == [
        {"rating_count": 10, "rating_scale": None, "source_game_id": "Q1"},
        {"rating_count": 20, "rating_scale": "100", "source_game_id": "328"},
    ]
