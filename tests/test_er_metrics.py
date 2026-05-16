from __future__ import annotations

import polars as pl

from src.entity_resolution.evaluate_model import compute_er_metrics


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
