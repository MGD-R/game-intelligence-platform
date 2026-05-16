from __future__ import annotations

from pathlib import Path

import polars as pl

from src.entity_resolution.corpus import SourceGameRecord
from src.preprocessing.export_ml_ready_base import write_parquet
from src.preprocessing.source_coverage import compute_coverage_metrics


def build_records() -> dict[tuple[str, str], SourceGameRecord]:
    rawg = SourceGameRecord(
        source="rawg",
        source_game_id="3498",
        name="Grand Theft Auto V",
        name_normalized="grand theft auto v",
        release_year=2013,
    )
    wikidata = SourceGameRecord(
        source="wikidata",
        source_game_id="Q12345",
        name="Grand Theft Auto V",
        name_normalized="grand theft auto v",
        release_year=2013,
        external_ids={"rawg": "3498", "steam": "271590", "igdb": "1020"},
    )
    return {
        ("rawg", "3498"): rawg,
        ("wikidata", "Q12345"): wikidata,
    }


def test_coverage_metrics_are_calculated() -> None:
    pairs = [
        {
            "source_a": "rawg",
            "source_id_a": "3498",
            "source_b": "wikidata",
            "source_id_b": "Q12345",
            "candidate_source": "external_id_positive",
            "label_source": "wikidata_rawg_external_id",
            "label_value": "1",
        }
    ]

    metrics, source_rows, external_id_rows, candidate_summary = compute_coverage_metrics(
        build_records(),
        pairs,
    )

    assert metrics["rawg_game_count"] == 1
    assert metrics["rawg_wikidata_matched_count"] == 1
    assert source_rows[0]["source"] == "rawg"
    assert any(row["external_source"] == "steam" for row in external_id_rows)
    assert candidate_summary["external_id_positive"] == 1


def test_export_helper_writes_parquet(tmp_path: Path) -> None:
    output_path = tmp_path / "pairs.parquet"

    write_parquet(output_path, [{"pair_id": "1", "source_a": "rawg"}])

    frame = pl.read_parquet(output_path)
    assert frame.height == 1
