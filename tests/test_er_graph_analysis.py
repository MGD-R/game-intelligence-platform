from __future__ import annotations

from src.entity_resolution.build_graph_analysis import (
    component_size_distribution_rows,
    high_probability_negative_rows,
    risky_component_rows,
    source_bridge_rows,
)
from src.entity_resolution.compare_merge_strategies import MergeStrategy
from src.entity_resolution.corpus import SourceGameRecord


def _records() -> dict[tuple[str, str], SourceGameRecord]:
    return {
        ("rawg", "1"): SourceGameRecord(
            source="rawg",
            source_game_id="1",
            name="Game One",
            name_normalized="game one",
            release_year=2020,
        ),
        ("igdb", "10"): SourceGameRecord(
            source="igdb",
            source_game_id="10",
            name="Game One",
            name_normalized="game one",
            release_year=2020,
        ),
        ("igdb", "11"): SourceGameRecord(
            source="igdb",
            source_game_id="11",
            name="Game One Deluxe",
            name_normalized="game one deluxe",
            release_year=2020,
        ),
    }


def test_component_size_distribution_buckets_component_sizes() -> None:
    strategy = MergeStrategy(name="test", description="test", mode="trusted")
    groups = [
        {("rawg", "1")},
        {("rawg", "2"), ("igdb", "2")},
        {("rawg", str(index)) for index in range(3, 7)},
    ]

    rows = component_size_distribution_rows(strategy, groups)

    assert rows == [
        {"strategy": "test", "component_size_bucket": "1", "component_count": 1},
        {"strategy": "test", "component_size_bucket": "2", "component_count": 1},
        {"strategy": "test", "component_size_bucket": "3-5", "component_count": 1},
    ]


def test_source_bridge_rows_counts_trusted_and_model_edges() -> None:
    strategy = MergeStrategy(name="test", description="test", mode="hybrid")
    trusted_edge = (("rawg", "1"), ("igdb", "10"))
    model_edge = (("rawg", "1"), ("igdb", "11"))

    rows = source_bridge_rows(strategy, {trusted_edge, model_edge}, {trusted_edge}, {model_edge})

    assert rows == [
        {
            "strategy": "test",
            "source_pair": "igdb <-> rawg",
            "edge_origin": "model",
            "edge_count": 1,
        },
        {
            "strategy": "test",
            "source_pair": "igdb <-> rawg",
            "edge_origin": "trusted",
            "edge_count": 1,
        },
    ]


def test_risky_component_rows_flags_same_source_duplicates_and_manual_negative() -> None:
    strategy = MergeStrategy(name="test", description="test", mode="model_only")
    records = _records()
    rows = [
        {
            "pair_id": "pair-1",
            "source_a": "rawg",
            "source_id_a": "1",
            "source_b": "igdb",
            "source_id_b": "11",
            "same_game_probability": 0.95,
            "review_status": "reviewed",
            "review_label": False,
        }
    ]
    groups = [{("rawg", "1"), ("igdb", "10"), ("igdb", "11")}]
    component_index = {key: 0 for key in groups[0]}
    model_edge = (("rawg", "1"), ("igdb", "11"))

    result = risky_component_rows(
        strategy,
        records,
        rows,
        groups,
        component_index,
        {model_edge},
        set(),
        {model_edge},
    )

    assert result[0]["same_source_duplicate_links"] == 1
    assert result[0]["manual_negative_pairs_in_component"] == 1
    assert result[0]["risk_score"] == 110
    assert result[0]["model_edge_count"] == 1


def test_high_probability_negative_rows_filters_reviewed_negatives() -> None:
    rows = [
        {
            "pair_id": "high-risk",
            "source_a": "rawg",
            "source_id_a": "1",
            "name_a": "Game One",
            "source_b": "igdb",
            "source_id_b": "11",
            "name_b": "Game One Deluxe",
            "candidate_source": "igdb_search",
            "same_game_probability": 0.91,
            "review_status": "reviewed",
            "review_label": False,
        },
        {
            "pair_id": "low-risk",
            "source_a": "rawg",
            "source_id_a": "2",
            "source_b": "igdb",
            "source_id_b": "12",
            "same_game_probability": 0.60,
            "review_status": "reviewed",
            "review_label": False,
        },
    ]

    result = high_probability_negative_rows(rows, min_probability=0.70)

    assert [row["pair_id"] for row in result] == ["high-risk"]
