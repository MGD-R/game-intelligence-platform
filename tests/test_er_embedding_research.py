from __future__ import annotations

import numpy as np
from scipy import sparse

from src.entity_resolution.build_embedding_research import (
    add_embedding_features,
    error_case_rows,
    pairwise_dense_cosine,
    pairwise_sparse_cosine,
    similarity_distribution_rows,
    svd_component_count,
)


def test_pairwise_sparse_cosine_uses_rowwise_dot_product() -> None:
    left = sparse.csr_matrix([[1.0, 0.0], [0.0, 1.0]])
    right = sparse.csr_matrix([[1.0, 0.0], [1.0, 0.0]])

    assert pairwise_sparse_cosine(left, right) == [1.0, 0.0]


def test_pairwise_dense_cosine_uses_rowwise_dot_product() -> None:
    left = np.asarray([[1.0, 0.0], [0.0, 1.0]])
    right = np.asarray([[0.5, 0.5], [0.0, 1.0]])

    assert pairwise_dense_cosine(left, right) == [0.5, 1.0]


def test_svd_component_count_keeps_valid_upper_bound() -> None:
    assert svd_component_count(document_count=10, feature_count=5, requested=64) == 4
    assert svd_component_count(document_count=1, feature_count=5, requested=64) == 0


def test_add_embedding_features_marks_manual_labels_and_similarity_scores() -> None:
    rows = [
        {
            "pair_id": "pair-1",
            "name_a": "Doom 3",
            "name_b": "Doom 3",
            "review_label": True,
            "release_year_diff": 0,
        },
        {
            "pair_id": "pair-2",
            "name_a": "Doom 3",
            "name_b": "Quake",
            "review_label": False,
            "release_year_diff": 1,
        },
    ]

    enriched = add_embedding_features(rows)

    assert enriched[0]["manual_label"] == 1
    assert enriched[1]["manual_label"] == 0
    assert enriched[0]["char_tfidf_cosine"] > enriched[1]["char_tfidf_cosine"]
    assert enriched[0]["same_release_year"] == 1
    assert enriched[1]["release_year_abs_diff"] == 1


def test_error_case_rows_selects_high_negative_and_low_positive_cases() -> None:
    rows = [
        {
            "pair_id": "false-positive-like",
            "manual_label": 0,
            "embedding_same_game_probability": 0.90,
        },
        {
            "pair_id": "false-negative-like",
            "manual_label": 1,
            "embedding_same_game_probability": 0.20,
        },
        {
            "pair_id": "clean",
            "manual_label": 1,
            "embedding_same_game_probability": 0.90,
        },
    ]

    result = error_case_rows(rows)

    assert [row["pair_id"] for row in result] == [
        "false-positive-like",
        "false-negative-like",
    ]


def test_similarity_distribution_rows_buckets_char_scores() -> None:
    rows = [{"char_tfidf_cosine": 0.05}, {"char_tfidf_cosine": 0.55}, {"char_tfidf_cosine": 1.0}]

    result = similarity_distribution_rows(rows)

    assert result == [
        {"char_tfidf_bucket": "0.0-0.1", "pair_count": 1},
        {"char_tfidf_bucket": "0.5-0.6", "pair_count": 1},
        {"char_tfidf_bucket": "1.0", "pair_count": 1},
    ]
