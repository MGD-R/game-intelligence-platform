from __future__ import annotations

from src.entity_resolution.compare_merge_strategies import (
    MergeStrategy,
    evaluate_strategy,
    is_trusted_canonical_edge,
    select_strategy_edges,
)
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
            name="Different Game",
            name_normalized="different game",
            release_year=2020,
        ),
    }


def test_trusted_canonical_edge_accepts_reviewed_positive() -> None:
    row = {
        "source_a": "rawg",
        "source_id_a": "1",
        "source_b": "igdb",
        "source_id_b": "10",
        "candidate_source": "igdb_search",
        "review_status": "reviewed",
        "review_label": True,
    }

    assert is_trusted_canonical_edge(row)


def test_model_only_strategy_keeps_manual_negative_as_false_positive_risk() -> None:
    rows = [
        {
            "pair_id": "pair-1",
            "source_a": "rawg",
            "source_id_a": "1",
            "source_b": "igdb",
            "source_id_b": "11",
            "name_a": "Game One",
            "name_b": "Different Game",
            "candidate_source": "igdb_search",
            "same_game_probability": 0.96,
            "review_status": "reviewed",
            "review_label": False,
        }
    ]
    strategy = MergeStrategy(
        name="model_auto_095",
        description="test",
        mode="model_only",
        threshold=0.95,
    )

    evaluation, risk_rows = evaluate_strategy(_records(), rows, strategy)

    assert evaluation.false_positive == 1
    assert evaluation.precision == 0
    assert risk_rows[0]["risk_type"] == "manual_negative_in_same_component"


def test_hybrid_strategy_blocks_manual_negative_model_edges() -> None:
    rows = [
        {
            "pair_id": "pair-1",
            "source_a": "rawg",
            "source_id_a": "1",
            "source_b": "igdb",
            "source_id_b": "11",
            "candidate_source": "igdb_search",
            "same_game_probability": 0.96,
            "name_similarity": 0.99,
            "release_year_diff": 0,
            "review_status": "reviewed",
            "review_label": False,
        }
    ]
    strategy = MergeStrategy(
        name="hybrid_safe_090",
        description="test",
        mode="hybrid",
        threshold=0.90,
        min_name_similarity=0.90,
        max_release_year_diff=2,
        manual_negative_blacklist=True,
    )

    edges, _trusted_edges, model_edges = select_strategy_edges(rows, strategy)
    evaluation, risk_rows = evaluate_strategy(_records(), rows, strategy)

    assert edges == set()
    assert model_edges == set()
    assert evaluation.true_negative == 1
    assert risk_rows == []
