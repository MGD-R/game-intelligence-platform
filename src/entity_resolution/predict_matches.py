"""Score candidate pairs with the baseline ER model and apply thresholds."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from typing import Any

import joblib
import polars as pl

from src.entity_resolution.io import (
    ensure_er_inputs,
    ensure_output_directories,
    feature_columns,
    load_candidate_pairs_frame,
    load_feature_base_frame,
)
from src.entity_resolution.thresholds import decision_from_probability, load_threshold_policy
from src.ingestion.repository import IngestionRepository
from src.preprocessing.export_ml_ready_base import write_parquet


def explanation_from_row(
    row: dict[str, Any],
    feature_names: list[str],
    coefficients: list[float],
) -> dict[str, Any]:
    contributions: list[tuple[str, float]] = []
    for name, coefficient in zip(feature_names, coefficients, strict=False):
        value = row.get(name)
        if value is None:
            continue
        try:
            contributions.append((name, float(value) * float(coefficient)))
        except (TypeError, ValueError):
            continue
    top = sorted(contributions, key=lambda item: abs(item[1]), reverse=True)[:3]
    return {"top_feature_contributions": [{name: round(score, 6)} for name, score in top]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Predict ER matches with baseline model.")
    parser.add_argument("--dry-run", action="store_true", help="Preview artifact paths only.")
    parser.add_argument("--allow-empty", action="store_true", help="Allow empty data state.")
    parser.add_argument("--limit", type=int, help="Optional row limit.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = ensure_output_directories()
    model_path = paths.models_dir / "logistic_regression_baseline.joblib"
    output_path = paths.predictions_dir / "predictions.parquet"
    if args.dry_run:
        print(
            {
                "model_path": str(model_path),
                "output_path": str(output_path),
                "allow_empty": args.allow_empty,
                "limit": args.limit,
            }
        )
        return 0

    ensure_er_inputs(allow_empty=args.allow_empty, allow_missing_artifacts=True)
    if not model_path.exists():
        if args.allow_empty:
            print({"prediction_count": 0, "skipped": True})
            return 0
        raise RuntimeError("Model artifact missing. Run `make er-train` first.")

    artifact = joblib.load(model_path)
    pipeline = artifact["pipeline"]
    feature_names = artifact["feature_names"]
    coefficients = pipeline.named_steps["model"].coef_[0].tolist()

    candidate_pairs = load_candidate_pairs_frame(limit=args.limit)
    feature_base = load_feature_base_frame(limit=args.limit)
    joined = candidate_pairs.join(feature_base, on="pair_id", how="inner")
    if joined.is_empty():
        if args.allow_empty:
            print({"prediction_count": 0, "skipped": True})
            return 0
        raise RuntimeError("Prediction input is empty. Run `make ml-ready-data` first.")

    prepared = joined.with_columns(
        [pl.col(column_name).cast(pl.Float64, strict=False) for column_name in feature_columns()]
    )
    probabilities = pipeline.predict_proba(prepared.select(feature_names).to_numpy())[:, 1].tolist()
    policy = load_threshold_policy()
    policy_json = asdict(policy)
    rows = []
    for row, probability in zip(prepared.to_dicts(), probabilities, strict=False):
        decision = decision_from_probability(probability, policy)
        explanation = explanation_from_row(row, feature_names, coefficients)
        rows.append(
            {
                **row,
                "same_game_probability": probability,
                "decision": decision,
                "model_name": "logistic_regression_baseline",
                "model_version": "v1",
                "threshold_policy_json": policy_json,
                "explanation_factors_json": explanation,
            }
        )

    repository = IngestionRepository()
    repository.upsert_entity_resolution_predictions(rows)
    write_parquet(output_path, rows)
    print({"output_path": str(output_path), "prediction_count": len(rows)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
