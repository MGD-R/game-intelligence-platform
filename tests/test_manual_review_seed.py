from __future__ import annotations

from src.entity_resolution.build_manual_review_seed import build_manual_review_rows
from src.entity_resolution.corpus import SourceGameRecord


def test_manual_review_seed_includes_pair_context() -> None:
    records = {
        ("rawg", "1"): SourceGameRecord(
            source="rawg",
            source_game_id="1",
            name="Game One",
            name_normalized="game one",
            release_year=2013,
        ),
        ("wikidata", "Q1"): SourceGameRecord(
            source="wikidata",
            source_game_id="Q1",
            name="Game One",
            name_normalized="game one",
            release_year=2014,
        ),
    }
    candidate_pairs = [
        {
            "pair_id": "pair-1",
            "source_a": "rawg",
            "source_id_a": "1",
            "source_b": "wikidata",
            "source_id_b": "Q1",
            "candidate_source": "same_normalized_name",
            "label_source": "wikidata_rawg_external_id",
            "label_value": "1",
            "confidence": 1.0,
        }
    ]
    features = {
        "pair-1": {
            "pair_id": "pair-1",
            "name_similarity": 1.0,
            "alias_similarity": 1.0,
            "release_year_diff": 1,
            "external_id_exact_match": True,
            "description_available_flag": False,
            "description_language_match": None,
            "source_count_signal": 2,
            "developer_overlap": 0,
            "publisher_overlap": 1,
            "features_json": {},
        }
    }

    rows = build_manual_review_rows(records, candidate_pairs, features)

    assert rows
    assert {row["review_category"] for row in rows} >= {
        "deterministic_positive",
        "same_title_different_year",
        "potential_conflict",
    }
    assert rows[0]["name_a"] == "Game One"
