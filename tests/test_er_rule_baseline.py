from __future__ import annotations

import polars as pl

from src.entity_resolution.rule_baseline import build_rule_predictions, score_rule_probability


def test_rule_baseline_returns_auto_merge_for_external_id_match() -> None:
    probability, reasons = score_rule_probability({"external_id_exact_match": True})

    assert probability >= 0.95
    assert "external_id_exact_match" in reasons


def test_rule_baseline_returns_no_merge_for_low_similarity_and_different_year() -> None:
    probability, _ = score_rule_probability(
        {
            "external_id_exact_match": False,
            "name_similarity": 0.2,
            "alias_similarity": 0.1,
            "release_year_diff": 6,
        }
    )

    assert probability < 0.70


def test_rule_predictions_include_decision_column() -> None:
    frame = pl.DataFrame(
        [
            {
                "pair_id": "pair-1",
                "external_id_exact_match": True,
                "name_similarity": 1.0,
                "alias_similarity": 1.0,
                "release_year_diff": 0,
            }
        ]
    )

    predictions = build_rule_predictions(frame)

    assert predictions["decision"].to_list() == ["auto_merge"]
