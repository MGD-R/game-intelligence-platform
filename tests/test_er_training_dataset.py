from __future__ import annotations

import polars as pl

from src.entity_resolution.build_training_dataset import build_training_frame


def test_training_dataset_builds_positive_and_conservative_negative_rows() -> None:
    candidate_pairs = pl.DataFrame(
        [
            {
                "pair_id": "pair-1",
                "source_a": "rawg",
                "source_id_a": "1",
                "source_b": "wikidata",
                "source_id_b": "Q1",
                "candidate_source": "external_id_positive",
                "label_source": "wikidata_rawg_external_id",
                "label_value": "1",
                "confidence": 1.0,
            },
            {
                "pair_id": "pair-2",
                "source_a": "rawg",
                "source_id_a": "2",
                "source_b": "wikidata",
                "source_id_b": "Q2",
                "candidate_source": "same_normalized_name",
                "label_source": None,
                "label_value": None,
                "confidence": 0.8,
            },
        ]
    )
    feature_base = pl.DataFrame(
        [
            {
                "pair_id": "pair-1",
                "name_similarity": 1.0,
                "alias_similarity": 1.0,
                "release_year_diff": 0,
                "external_id_exact_match": True,
                "developer_overlap": 1.0,
                "publisher_overlap": 1.0,
                "platform_jaccard": 1.0,
                "genre_jaccard": 1.0,
                "tag_jaccard": 1.0,
                "description_available_flag": True,
                "description_language_match": True,
                "source_count_signal": 3,
            },
            {
                "pair_id": "pair-2",
                "name_similarity": 0.2,
                "alias_similarity": 0.1,
                "release_year_diff": 5,
                "external_id_exact_match": False,
                "developer_overlap": 0.0,
                "publisher_overlap": 0.0,
                "platform_jaccard": 0.0,
                "genre_jaccard": 0.0,
                "tag_jaccard": 0.0,
                "description_available_flag": False,
                "description_language_match": False,
                "source_count_signal": 2,
            },
        ]
    )
    source_games = pl.DataFrame(
        [
            {"source": "rawg", "source_game_id": "1", "name": "Game One", "release_year": 2013},
            {
                "source": "wikidata",
                "source_game_id": "Q1",
                "name": "Game One",
                "release_year": 2013,
            },
            {"source": "rawg", "source_game_id": "2", "name": "Game Two", "release_year": 2010},
            {
                "source": "wikidata",
                "source_game_id": "Q2",
                "name": "Different Game",
                "release_year": 2015,
            },
        ]
    )

    training = build_training_frame(candidate_pairs, feature_base, source_games)

    assert training.filter(pl.col("label") == 1).height == 1
    assert training.filter(pl.col("label") == 0).height == 1
    assert training.filter(pl.col("label") == 0)["synthetic_negative_rule"].to_list() == [
        "different_external_ids"
    ]


def test_training_dataset_manual_labels_override_weak_labels() -> None:
    candidate_pairs = pl.DataFrame(
        [
            {
                "pair_id": "pair-1",
                "source_a": "rawg",
                "source_id_a": "1",
                "source_b": "wikidata",
                "source_id_b": "Q1",
                "candidate_source": "external_id",
                "label_source": "wikidata_rawg_external_id",
                "label_value": "1",
                "confidence": 1.0,
            }
        ]
    )
    feature_base = pl.DataFrame(
        [
            {
                "pair_id": "pair-1",
                "name_similarity": 1.0,
                "alias_similarity": 1.0,
                "release_year_diff": 0,
                "external_id_exact_match": True,
                "developer_overlap": 1.0,
                "publisher_overlap": 1.0,
                "platform_jaccard": 1.0,
                "genre_jaccard": 1.0,
                "tag_jaccard": 1.0,
                "description_available_flag": True,
                "description_language_match": True,
                "source_count_signal": 3,
            }
        ]
    )
    manual_review_labels = pl.DataFrame([{"pair_id": "pair-1", "manual_label": 0}])

    training = build_training_frame(
        candidate_pairs,
        feature_base,
        manual_review_labels=manual_review_labels,
    )

    assert training["label"].to_list() == [0]
    assert training["training_label_source"].to_list() == ["manual_review"]


def test_training_dataset_excludes_invalid_display_names() -> None:
    candidate_pairs = pl.DataFrame(
        [
            {
                "pair_id": "pair-1",
                "source_a": "rawg",
                "source_id_a": "1",
                "source_b": "wikidata",
                "source_id_b": "Q1",
                "candidate_source": "external_id",
                "label_source": "wikidata_rawg_external_id",
                "label_value": "1",
                "confidence": 1.0,
            },
            {
                "pair_id": "pair-2",
                "source_a": "rawg",
                "source_id_a": "2",
                "source_b": "igdb",
                "source_id_b": "10",
                "candidate_source": "igdb_search",
                "label_source": None,
                "label_value": None,
                "confidence": 0.9,
            },
        ]
    )
    feature_base = pl.DataFrame(
        [
            {
                "pair_id": pair_id,
                "name_similarity": 1.0,
                "alias_similarity": 1.0,
                "release_year_diff": 0,
                "external_id_exact_match": True,
                "developer_overlap": 1.0,
                "publisher_overlap": 1.0,
                "platform_jaccard": 1.0,
                "genre_jaccard": 1.0,
                "tag_jaccard": 1.0,
                "description_available_flag": True,
                "description_language_match": True,
                "source_count_signal": 3,
            }
            for pair_id in ("pair-1", "pair-2")
        ]
    )
    source_games = pl.DataFrame(
        [
            {"source": "rawg", "source_game_id": "1", "name": "Known Game", "release_year": 2018},
            {"source": "wikidata", "source_game_id": "Q1", "name": "Q12345", "release_year": 2018},
            {"source": "rawg", "source_game_id": "2", "name": "Valid Game", "release_year": 2020},
            {"source": "igdb", "source_game_id": "10", "name": "Valid Game", "release_year": 2020},
        ]
    )

    training = build_training_frame(candidate_pairs, feature_base, source_games)

    assert training["pair_id"].to_list() == ["pair-2"]
