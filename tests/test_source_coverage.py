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
        source_game_rows=[
            {
                "source": "steam",
                "source_game_id": "271590",
                "quality_flags_json": {"has_supported_languages": True},
            }
        ],
        description_rows=[
            {
                "source": "steam",
                "source_game_id": "271590",
                "description_type": "short_description",
                "description_text": "Open world action game.",
            },
            {
                "source": "wikipedia",
                "source_game_id": "12345",
                "description_type": "summary",
                "language": "ru",
                "description_text": "Краткая справка.",
            }
        ],
        rating_rows=[
            {
                "source": "steam",
                "source_game_id": "271590",
                "rating_type": "steam_metacritic",
                "rating_value": 96,
            }
        ],
        popularity_rows=[
            {
                "source": "steam",
                "source_game_id": "271590",
                "metric_name": "recommendations_total",
                "metric_value": 1782345,
            }
        ],
        url_rows=[
            {
                "source": "wikipedia",
                "source_game_id": "12345",
                "url_type": "page",
                "url": (
                    "https://ru.wikipedia.org/wiki/"
                    "%D0%9F%D1%80%D0%B8%D0%BC%D0%B5%D1%80_%D0%B8%D0%B3%D1%80%D1%8B"
                ),
                "source_specific_json": {"language": "ru"},
            }
        ],
    )

    assert metrics["rawg_game_count"] == 1
    assert metrics["rawg_wikidata_matched_count"] == 1
    assert metrics["wikidata_steam_appid_count"] == 1
    assert metrics["steam_with_short_description_count"] == 1
    assert metrics["wikipedia_page_count"] == 1
    assert metrics["wikipedia_ru_page_count"] == 1
    assert metrics["wikipedia_summary_count"] == 1
    assert source_rows[0]["source"] == "rawg"
    assert any(row["external_source"] == "steam" for row in external_id_rows)
    assert candidate_summary["external_id_positive"] == 1


def test_export_helper_writes_parquet(tmp_path: Path) -> None:
    output_path = tmp_path / "pairs.parquet"

    write_parquet(output_path, [{"pair_id": "1", "source_a": "rawg"}])

    frame = pl.read_parquet(output_path)
    assert frame.height == 1
