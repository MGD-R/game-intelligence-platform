from datetime import date
from pathlib import Path
from uuid import uuid4

import polars as pl

from src.preprocessing.export_ml_ready_base import write_parquet


def test_export_analysis_helper_writes_parquet(tmp_path: Path) -> None:
    output_path = tmp_path / "source_games.parquet"
    write_parquet(output_path, [{"source": "rawg", "source_game_id": "1"}])
    frame = pl.read_parquet(output_path)
    assert frame.height == 1


def test_export_analysis_helper_normalizes_uuid_values(tmp_path: Path) -> None:
    output_path = tmp_path / "candidate_pairs.parquet"
    pair_id = uuid4()

    write_parquet(output_path, [{"pair_id": pair_id, "source_a": "rawg"}])

    frame = pl.read_parquet(output_path)
    assert frame.item(0, "pair_id") == str(pair_id)


def test_export_analysis_helper_coerces_schema_values(tmp_path: Path) -> None:
    output_path = tmp_path / "source_games_schema.parquet"

    write_parquet(
        output_path,
        [{"source": "rawg", "release_date": date(2017, 3, 20), "release_year": 2017}],
        schema={"source": pl.Utf8, "release_date": pl.Utf8, "release_year": pl.Int64},
    )

    frame = pl.read_parquet(output_path)
    assert frame.item(0, "release_date") == "2017-03-20"
