from __future__ import annotations

import pytest

from src.recommendations.build_bayesian_rating_analysis import (
    bayesian_average,
    build_canonical_bayesian_rows,
    normalize_rating,
)


def test_normalize_rating_maps_source_scale_to_100() -> None:
    assert normalize_rating(4.5, 5) == 90
    assert normalize_rating(110, 100) == 100
    assert normalize_rating(-10, 100) == 0


def test_bayesian_average_shrinks_low_vote_rating_to_global_mean() -> None:
    adjusted = bayesian_average(rating=100, vote_count=1, global_mean=70, prior_votes=50)

    assert round(adjusted, 6) == round(((1 * 100) + (50 * 70)) / 51, 6)
    assert adjusted < 100


def test_bayesian_average_rejects_invalid_counts() -> None:
    with pytest.raises(ValueError):
        bayesian_average(rating=80, vote_count=-1, global_mean=70, prior_votes=50)


def test_build_canonical_bayesian_rows_aggregates_vote_weighted_ratings() -> None:
    rows = [
        {
            "canonical_game_id": "game-1",
            "canonical_name": "Game One",
            "release_year": 2020,
            "rating_value": 4.0,
            "rating_scale": "5",
            "rating_count": 100,
            "rating_type": "rawg_rating",
        },
        {
            "canonical_game_id": "game-1",
            "canonical_name": "Game One",
            "release_year": 2020,
            "rating_value": 90.0,
            "rating_scale": "100",
            "rating_count": 100,
            "rating_type": "igdb_rating",
        },
        {
            "canonical_game_id": "game-2",
            "canonical_name": "Game Two",
            "release_year": 2021,
            "rating_value": 50.0,
            "rating_scale": "100",
            "rating_count": 10,
            "rating_type": "igdb_rating",
        },
    ]

    result_rows, summary = build_canonical_bayesian_rows(rows, prior_votes=50)

    assert summary["rating_input_count"] == 3
    assert summary["canonical_game_count"] == 2
    assert result_rows[0]["canonical_name"] == "Game One"
    assert result_rows[0]["naive_weighted_rating"] == 85
    assert result_rows[0]["vote_count"] == 200
