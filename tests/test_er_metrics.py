from __future__ import annotations

import polars as pl

from src.entity_resolution.evaluate_model import compute_er_metrics, with_label_column


def test_metrics_handle_single_class_edge_case_gracefully() -> None:
    frame = pl.DataFrame(
        [
            {
                "label": 1,
                "same_game_probability": 0.99,
                "decision": "auto_merge",
            }
        ]
    )

    metrics = compute_er_metrics(frame)

    assert metrics["roc_auc"] is None
    assert metrics["pr_auc"] is None
    assert metrics["warnings"]


def test_metrics_derive_label_column_from_prediction_label_value() -> None:
    frame = pl.DataFrame(
        [
            {
                "label_value": "1",
                "same_game_probability": 0.99,
                "decision": "auto_merge",
            },
            {
                "label_value": None,
                "same_game_probability": 0.2,
                "decision": "no_merge",
            },
        ]
    )

    normalized = with_label_column(frame)

    assert normalized["label"].to_list() == [1, None]
