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
        ("wikipedia", "12345"): SourceGameRecord(
            source="wikipedia",
            source_game_id="12345",
            name="Game One",
            name_normalized="game one",
            release_year=None,
            has_description=True,
        ),
        ("igdb", "1020"): SourceGameRecord(
            source="igdb",
            source_game_id="1020",
            name="Game One",
            name_normalized="game one",
            release_year=2013,
            external_ids={"steam": "271590"},
            tags={"crime"},
            themes={"open world"},
            developers={"Rockstar North"},
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
        alias_rows=[
            {
                "source": "igdb",
                "source_game_id": "1020",
                "alias_type": "igdb_localization",
                "alias": "Game One RU",
            }
        ],
        description_rows=[
            {
                "source": "steam",
                "source_game_id": "10",
                "description_type": "short_description",
                "description_text": "Short description",
            },
            {
                "source": "wikipedia",
                "source_game_id": "12345",
                "description_type": "summary",
                "description_text": "Short wiki summary",
                "language": "en",
            },
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
        url_rows=[
            {
                "source": "wikipedia",
                "source_game_id": "12345",
                "url_type": "page",
                "url": "https://en.wikipedia.org/wiki/Sample_Game",
                "source_specific_json": {"language": "en"},
            }
        ],
    )
    assert summary["record_count_by_source"]["rawg"] == 1
    assert summary["source_overlap_count"] == 1
    assert summary["conflict_count_by_field"]["release_year"] == 1
    assert summary["candidate_pair_summary"]["external_id_positive"] == 1
    assert 0.0 <= summary["missing_release_date_rate"] <= 1.0
    assert 0.0 <= summary["missing_description_rate"] <= 1.0
    assert 0.0 <= summary["missing_developer_rate"] <= 1.0
    assert 0.0 <= summary["missing_genre_rate"] <= 1.0
    assert 0.0 <= summary["missing_platform_rate"] <= 1.0
    assert summary["steam_game_count"] == 1
    assert summary["steam_with_metacritic_count"] == 1
    assert summary["igdb_game_count"] == 1
    assert summary["igdb_with_localizations_count"] == 1
    assert summary["wikipedia_page_count"] == 1
    assert summary["wikipedia_summary_count"] == 1
    assert summary["short_wikipedia_extract_count"] == 1
