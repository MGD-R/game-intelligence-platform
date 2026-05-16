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
    summary = compute_data_quality_metrics(build_records(), pairs)
    assert summary["record_count_by_source"]["rawg"] == 1
    assert summary["source_overlap_count"] == 1
    assert summary["conflict_count_by_field"]["release_year"] == 1
    assert summary["candidate_pair_summary"]["external_id_positive"] == 1
