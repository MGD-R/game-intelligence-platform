"""Evaluate baseline ER predictions where labels exist."""

from __future__ import annotations

import argparse
import json
from typing import Any

import polars as pl
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from src.entity_resolution.io import ensure_output_directories


def with_label_column(frame: pl.DataFrame) -> pl.DataFrame:
    if "label" in frame.columns:
        return frame
    if "label_value" not in frame.columns:
        return frame.with_columns(pl.lit(None, dtype=pl.Int64).alias("label"))
    return frame.with_columns(
        pl.when(pl.col("label_value") == "1")
        .then(pl.lit(1))
        .when(pl.col("label_value") == "0")
        .then(pl.lit(0))
        .otherwise(pl.lit(None, dtype=pl.Int64))
        .alias("label")
    )


def compute_er_metrics(frame: pl.DataFrame) -> dict[str, Any]:
    frame = with_label_column(frame)
    labeled = frame.filter(pl.col("label").is_not_null())
    if labeled.is_empty():
        return {
            "precision": None,
            "recall": None,
            "f1": None,
            "roc_auc": None,
            "pr_auc": None,
            "confusion_matrix": None,
            "warnings": ["no labeled predictions available"],
            "auto_merge_rate": 0.0,
            "manual_review_rate": 0.0,
            "no_merge_rate": 0.0,
            "positive_label_count": 0,
            "negative_label_count": 0,
            "training_row_count": 0,
            "test_row_count": 0,
        }

    y_true = labeled["label"].cast(pl.Int64).to_list()
    y_prob = labeled["same_game_probability"].cast(pl.Float64).to_list()
    y_pred = [1 if probability >= 0.5 else 0 for probability in y_prob]
    metrics: dict[str, Any] = {
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 6),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 6),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 6),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist(),
        "auto_merge_rate": round(
            frame.filter(pl.col("decision") == "auto_merge").height / max(frame.height, 1),
            6,
        ),
        "manual_review_rate": round(
            frame.filter(pl.col("decision") == "manual_review").height / max(frame.height, 1),
            6,
        ),
        "no_merge_rate": round(
            frame.filter(pl.col("decision") == "no_merge").height / max(frame.height, 1),
            6,
        ),
        "positive_label_count": int(sum(y_true)),
        "negative_label_count": int(len(y_true) - sum(y_true)),
        "training_row_count": int(frame.height),
        "test_row_count": int(labeled.height),
    }
    if len(set(y_true)) >= 2:
        metrics["roc_auc"] = round(float(roc_auc_score(y_true, y_prob)), 6)
        metrics["pr_auc"] = round(float(average_precision_score(y_true, y_prob)), 6)
        metrics["warnings"] = []
    else:
        metrics["roc_auc"] = None
        metrics["pr_auc"] = None
        metrics["warnings"] = ["single-class labeled predictions"]
    return metrics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate baseline ER predictions.")
    parser.add_argument("--dry-run", action="store_true", help="Preview report paths only.")
    parser.add_argument("--allow-empty", action="store_true", help="Allow empty predictions.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = ensure_output_directories()
    predictions_path = paths.predictions_dir / "predictions.parquet"
    metrics_path = paths.reports_dir / "metrics.json"
    summary_path = paths.reports_dir / "summary.md"
    if args.dry_run:
        print(
            {
                "predictions_path": str(predictions_path),
                "metrics_path": str(metrics_path),
                "summary_path": str(summary_path),
            }
        )
        return 0

    if not predictions_path.exists():
        if args.allow_empty:
            print({"evaluation_skipped": True})
            return 0
        raise RuntimeError("Predictions artifact missing. Run `make er-predict` first.")

    frame = pl.read_parquet(predictions_path)
    metrics = compute_er_metrics(frame)
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_lines = ["# Entity Resolution Baseline Summary", ""]
    for key, value in metrics.items():
        summary_lines.append(f"- {key}: {value}")
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print({"metrics_path": str(metrics_path), "summary_path": str(summary_path)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
