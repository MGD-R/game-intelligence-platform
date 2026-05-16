from pathlib import Path

import polars as pl

from src.preprocessing.export_ml_ready_base import write_parquet


def test_export_analysis_helper_writes_parquet(tmp_path: Path) -> None:
    output_path = tmp_path / "source_games.parquet"
    write_parquet(output_path, [{"source": "rawg", "source_game_id": "1"}])
    frame = pl.read_parquet(output_path)
    assert frame.height == 1
