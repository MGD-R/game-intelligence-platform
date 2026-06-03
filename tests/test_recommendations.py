from __future__ import annotations

from src.recommendations.build_recommendations import (
    CanonicalGameFeatures,
    build_recommendation_rows,
    weighted_jaccard,
)


def test_weighted_jaccard_scores_shared_weighted_features() -> None:
    left = {"genre:action": 3.0, "platform:pc": 0.5}
    right = {"genre:action": 3.0, "tag:indie": 1.0}

    assert round(weighted_jaccard(left, right), 6) == 0.666667


def test_build_recommendation_rows_ranks_similar_games() -> None:
    games = [
        CanonicalGameFeatures(
            canonical_game_id="00000000-0000-0000-0000-000000000001",
            canonical_name="Game A",
            release_year=2020,
            features={"genre:action": 3.0, "tag:co-op": 1.0, "platform:pc": 0.5},
        ),
        CanonicalGameFeatures(
            canonical_game_id="00000000-0000-0000-0000-000000000002",
            canonical_name="Game B",
            release_year=2021,
            features={"genre:action": 3.0, "tag:co-op": 1.0, "platform:pc": 0.5},
        ),
        CanonicalGameFeatures(
            canonical_game_id="00000000-0000-0000-0000-000000000003",
            canonical_name="Game C",
            release_year=2022,
            features={"genre:puzzle": 3.0, "platform:pc": 0.5},
        ),
    ]

    rows = build_recommendation_rows(
        games,
        top_k=1,
        max_block_size=10,
        max_candidates_per_game=10,
        min_score=0.2,
    )

    assert rows[0]["canonical_game_id"] == games[0].canonical_game_id
    assert rows[0]["recommended_canonical_game_id"] == games[1].canonical_game_id
    assert rows[0]["rank"] == 1
    assert rows[0]["score"] == 1.0
