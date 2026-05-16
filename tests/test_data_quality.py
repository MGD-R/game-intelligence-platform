from src.entity_resolution.corpus import SourceGameRecord
from src.preprocessing.data_quality import compute_data_quality_metrics


def build_records() -> dict[tuple[str, str], SourceGameRecord]:
    return {
        ("rawg", "1"): SourceGameRecord(
            source="rawg",
            source_game_id="1",
            name="Game One",
            name_normalized="game one",
            release_year=2013,
            genres={"action"},
            platforms={"pc"},
            has_description=True,
        ),
        ("wikidata", "Q1"): SourceGameRecord(
            source="wikidata",
            source_game_id="Q1",
            name="Game One",
            name_normalized="game one",
            release_year=2014,
            external_ids={"rawg": "1"},
            alias_languages={"ru": {"игра один"}, "en": {"game one"}},
        ),
        ("steam", "10"): SourceGameRecord(
            source="steam",
            source_game_id="10",
            name="Game One",
            name_normalized="game one",
            release_year=2013,
            external_ids={"steam": "10"},
            has_description=True,
        ),
    }


def test_quality_metrics_calculate_missingness_and_conflicts() -> None:
    pairs = [
        {
            "source_a": "rawg",
            "source_id_a": "1",
            "source_b": "wikidata",
            "source_id_b": "Q1",
            "candidate_source": "external_id_positive",
            "label_source": "wikidata_rawg_external_id",
            "label_value": "1",
        }
    ]
    summary = compute_data_quality_metrics(
        build_records(),
        pairs,
        source_game_rows=[
            {
                "source": "steam",
                "source_game_id": "10",
                "quality_flags_json": {"has_supported_languages": True},
            }
        ],
        description_rows=[
            {
                "source": "steam",
                "source_game_id": "10",
                "description_type": "short_description",
                "description_text": "Short description",
            }
        ],
        rating_rows=[
            {
                "source": "steam",
                "source_game_id": "10",
                "rating_type": "steam_metacritic",
                "rating_value": 95,
            }
        ],
        popularity_rows=[
            {
                "source": "steam",
                "source_game_id": "10",
                "metric_name": "recommendations_total",
                "metric_value": 10,
            }
        ],
    )
    assert summary["record_count_by_source"]["rawg"] == 1
    assert summary["source_overlap_count"] == 1
    assert summary["conflict_count_by_field"]["release_year"] == 1
    assert summary["candidate_pair_summary"]["external_id_positive"] == 1
    assert summary["steam_game_count"] == 1
    assert summary["steam_with_metacritic_count"] == 1
