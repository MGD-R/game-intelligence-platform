"""Train a Logistic Regression ER baseline on weak labels and safe negatives."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import polars as pl
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from src.entity_resolution.build_training_dataset import build_training_frame
from src.entity_resolution.io import (
    ensure_er_inputs,
    ensure_output_directories,
    feature_columns,
    load_candidate_pairs_frame,
    load_entity_resolution_config,
    load_feature_base_frame,
    load_reviewed_manual_labels_frame,
    load_source_games_frame,
)
from src.entity_resolution.thresholds import decision_from_probability, load_threshold_policy
from src.preprocessing.export_ml_ready_base import write_parquet


def prepare_feature_matrix(
    frame: pl.DataFrame,
) -> tuple[list[str], list[list[float | None]], list[int]]:
    features = feature_columns()
    prepared = frame.with_columns(
        [
            pl.col(column_name).cast(pl.Float64, strict=False).alias(column_name)
            for column_name in features
        ]
    )
    X = prepared.select(features).to_numpy().tolist()
    y = prepared["label"].cast(pl.Int64).to_list()
    return features, X, y


def compute_metrics(y_true: list[int], y_pred: list[int], y_prob: list[float]) -> dict[str, Any]:
    unique_labels = set(y_true)
    metrics: dict[str, Any] = {
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 6),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 6),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 6),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
    }
    if len(unique_labels) >= 2:
        metrics["roc_auc"] = round(float(roc_auc_score(y_true, y_prob)), 6)
        metrics["pr_auc"] = round(float(average_precision_score(y_true, y_prob)), 6)
    else:
        metrics["roc_auc"] = None
        metrics["pr_auc"] = None
        metrics["warnings"] = ["single-class evaluation set"]
    return metrics


def compute_metrics_for_rows(
    rows: list[dict[str, Any]],
    y_prob: list[float],
    *,
    label_source: str,
) -> dict[str, Any]:
    indexes = [
        index
        for index, row in enumerate(rows)
        if str(row.get("training_label_source") or "") == label_source
    ]
    if not indexes:
        return {
            "label_source": label_source,
            "row_count": 0,
            "warnings": [f"no {label_source} rows in evaluation split"],
        }
    y_true = [int(rows[index]["label"]) for index in indexes]
    probabilities = [float(y_prob[index]) for index in indexes]
    y_pred = [1 if probability >= 0.5 else 0 for probability in probabilities]
    metrics = compute_metrics(y_true, y_pred, probabilities)
    metrics["label_source"] = label_source
    metrics["row_count"] = len(indexes)
    metrics["positive_label_count"] = int(sum(y_true))
    metrics["negative_label_count"] = int(len(y_true) - sum(y_true))
    return metrics


def label_source_counts(frame: pl.DataFrame) -> list[dict[str, Any]]:
    if "training_label_source" not in frame.columns:
        return []
    return frame.group_by("training_label_source").len().sort("training_label_source").to_dicts()


def maybe_log_mlflow(enabled: bool, metrics: dict[str, Any], model_name: str) -> list[str]:
    warnings: list[str] = []
    if not enabled:
        return warnings
    try:
        import mlflow
    except ImportError:
        return ["mlflow not installed; skipped logging"]

    try:
        with mlflow.start_run(run_name=model_name):
            for key, value in metrics.items():
                if isinstance(value, (int, float)) and value is not None:
                    mlflow.log_metric(key, float(value))
    except Exception as exc:  # pragma: no cover - optional runtime path
        warnings.append(f"mlflow logging skipped: {exc}")
    return warnings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train baseline Logistic Regression ER model.")
    parser.add_argument("--dry-run", action="store_true", help="Preview artifact paths only.")
    parser.add_argument("--allow-empty", action="store_true", help="Allow empty dataset state.")
    parser.add_argument("--limit", type=int, help="Optional row limit.")
    parser.add_argument("--log-mlflow", action="store_true", help="Log to MLflow if available.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = ensure_output_directories()
    model_path = paths.models_dir / "logistic_regression_baseline.joblib"
    feature_list_path = paths.models_dir / "feature_list.json"
    metrics_path = paths.reports_dir / "metrics.json"
    coefficients_path = paths.reports_dir / "feature_coefficients.csv"
    predictions_path = paths.predictions_dir / "predictions.parquet"

    if args.dry_run:
        print(
            {
                "model_path": str(model_path),
                "metrics_path": str(metrics_path),
                "predictions_path": str(predictions_path),
                "allow_empty": args.allow_empty,
                "limit": args.limit,
                "log_mlflow": args.log_mlflow,
            }
        )
        return 0

    ensure_er_inputs(allow_empty=args.allow_empty, allow_missing_artifacts=True)
    training_frame = build_training_frame(
        load_candidate_pairs_frame(limit=args.limit),
        load_feature_base_frame(limit=args.limit),
        load_source_games_frame(limit=args.limit),
        load_reviewed_manual_labels_frame(limit=args.limit),
    )
    if training_frame.is_empty():
        if args.allow_empty:
            print({"training_row_count": 0, "skipped": True})
            return 0
        raise RuntimeError("Training dataset is empty. Run `make ml-ready-data` first.")

    if training_frame["label"].n_unique() < 2:
        raise RuntimeError("Not enough label diversity to train. More labels are needed.")
    label_counts = training_frame.group_by("label").len().to_dicts()
    if any(int(row["len"]) < 2 for row in label_counts):
        raise RuntimeError("Not enough positive/negative rows to split train/test safely.")

    feature_names, X, y = prepare_feature_matrix(training_frame)
    config = load_entity_resolution_config()
    model_cfg = config.get("model", {}).get("logistic_regression", {})

    stratify = y if len(set(y)) > 1 else None
    X_train, X_test, y_train, y_test, train_rows, test_rows = train_test_split(
        X,
        y,
        training_frame.to_dicts(),
        test_size=0.4,
        random_state=int(model_cfg.get("random_state", 42)),
        stratify=stratify,
    )

    pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                LogisticRegression(
                    class_weight=model_cfg.get("class_weight", "balanced"),
                    max_iter=int(model_cfg.get("max_iter", 1000)),
                    random_state=int(model_cfg.get("random_state", 42)),
                ),
            ),
        ]
    )
    pipeline.fit(X_train, y_train)
    y_prob = pipeline.predict_proba(X_test)[:, 1].tolist()
    y_pred = [1 if probability >= 0.5 else 0 for probability in y_prob]
    metrics = compute_metrics(y_test, y_pred, y_prob)
    metrics.update(
        {
            "training_row_count": len(train_rows),
            "test_row_count": len(test_rows),
            "positive_label_count": int(sum(y)),
            "negative_label_count": int(len(y) - sum(y)),
            "training_label_source_counts": label_source_counts(training_frame),
            "test_manual_review_metrics": compute_metrics_for_rows(
                test_rows,
                y_prob,
                label_source="manual_review",
            ),
        }
    )
    mlflow_warnings = maybe_log_mlflow(args.log_mlflow, metrics, "logistic_regression_baseline")
    if mlflow_warnings:
        metrics.setdefault("warnings", []).extend(mlflow_warnings)

    joblib.dump({"pipeline": pipeline, "feature_names": feature_names}, model_path)
    feature_list_path.write_text(json.dumps(feature_names, indent=2) + "\n", encoding="utf-8")
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    policy = load_threshold_policy()
    prediction_rows = []
    for row, probability, predicted_label in zip(test_rows, y_prob, y_pred, strict=False):
        prediction_rows.append(
            {
                **row,
                "same_game_probability": probability,
                "predicted_label": predicted_label,
                "decision": decision_from_probability(probability, policy),
                "model_name": "logistic_regression_baseline",
                "model_version": "v1",
            }
        )
    write_parquet(predictions_path, prediction_rows)

    coefficients = pipeline.named_steps["model"].coef_[0]
    coefficient_rows = [
        {"feature_name": name, "coefficient": float(value)}
        for name, value in zip(feature_names, coefficients, strict=False)
    ]
    Path(coefficients_path).parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(coefficient_rows).write_csv(coefficients_path)
    print({"model_path": str(model_path), "metrics_path": str(metrics_path)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
