from __future__ import annotations

import polars as pl

from src.entity_resolution.build_manual_review_queue import build_review_queue


def test_manual_review_queue_sorts_borderline_examples_first() -> None:
    frame = pl.DataFrame(
        [
            {
                "source_a": "rawg",
                "source_id_a": "1",
                "name_a": "Game A",
                "release_year_a": 2013,
                "source_b": "wikidata",
                "source_id_b": "Q1",
                "name_b": "Game A",
                "release_year_b": 2014,
                "same_game_probability": 0.71,
                "decision": "manual_review",
                "explanation_factors_json": "{}",
                "candidate_source": "same_normalized_name",
                "label_source": None,
            },
            {
                "source_a": "rawg",
                "source_id_a": "2",
                "name_a": "Game B",
                "release_year_a": 2010,
                "source_b": "wikidata",
                "source_id_b": "Q2",
                "name_b": "Game B",
                "release_year_b": 2010,
                "same_game_probability": 0.93,
                "decision": "manual_review",
                "explanation_factors_json": "{}",
                "candidate_source": "same_release_year_and_similar_name",
                "label_source": None,
            },
        ]
    )

    queue = build_review_queue(frame)

    assert queue["source_id_a"].to_list()[0] == "2"
