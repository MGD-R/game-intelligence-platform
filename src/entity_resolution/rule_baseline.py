"""Transparent rule-based entity-resolution baseline."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import polars as pl

from src.entity_resolution.build_training_dataset import build_training_frame
from src.entity_resolution.io import (
    ensure_er_inputs,
    load_candidate_pairs_frame,
    load_feature_base_frame,
    load_source_games_frame,
    resolve_entity_resolution_paths,
)
from src.entity_resolution.thresholds import decision_from_probability, load_threshold_policy
from src.preprocessing.export_ml_ready_base import write_parquet


def score_rule_probability(row: dict[str, Any]) -> tuple[float, list[str]]:
    reasons: list[str] = []
    name_similarity = float(row.get("name_similarity") or 0.0)
    alias_similarity = float(row.get("alias_similarity") or 0.0)
    release_year_diff = row.get("release_year_diff")
    release_year_diff = int(release_year_diff) if release_year_diff is not None else None
    external_id_exact_match = bool(row.get("external_id_exact_match"))
    developer_overlap = float(row.get("developer_overlap") or 0.0)
    platform_jaccard = float(row.get("platform_jaccard") or 0.0)

    if external_id_exact_match:
        reasons.append("external_id_exact_match")
        return 0.99, reasons
    if name_similarity >= 0.97 and (release_year_diff is None or release_year_diff <= 1):
        reasons.extend(["very_high_name_similarity", "compatible_release_year"])
        return 0.97, reasons
    if alias_similarity >= 0.97 and (release_year_diff is None or release_year_diff <= 1):
        reasons.extend(["high_alias_similarity", "compatible_release_year"])
        return 0.96, reasons
    if name_similarity < 0.35 and release_year_diff is not None and release_year_diff >= 2:
        reasons.extend(["low_name_similarity", "different_release_year"])
        return 0.05, reasons

    score = 0.15
    if name_similarity:
        score += name_similarity * 0.45
        reasons.append("name_similarity")
    if alias_similarity:
        score += alias_similarity * 0.15
        reasons.append("alias_similarity")
    if release_year_diff == 0:
        score += 0.15
        reasons.append("same_release_year")
    elif release_year_diff is not None and release_year_diff >= 5:
        score -= 0.1
        reasons.append("release_year_conflict")
    if developer_overlap >= 0.5:
        score += 0.05
        reasons.append("developer_overlap")
    if platform_jaccard >= 0.5:
        score += 0.05
        reasons.append("platform_overlap")

    return max(0.0, min(round(score, 6), 0.94)), reasons


def build_rule_predictions(frame: pl.DataFrame) -> pl.DataFrame:
    policy = load_threshold_policy()
    rows: list[dict[str, Any]] = []
    for row in frame.to_dicts():
        probability, reasons = score_rule_probability(row)
        rows.append(
            {
                **row,
                "model_name": "rule_baseline",
                "model_version": "v1",
                "same_game_probability": probability,
                "decision": decision_from_probability(probability, policy),
                "explanation_factors_json": {"reasons": reasons},
            }
        )
    return pl.DataFrame(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run rule-based ER baseline.")
    parser.add_argument("--dry-run", action="store_true", help="Preview output paths only.")
    parser.add_argument("--allow-empty", action="store_true", help="Allow empty input state.")
    parser.add_argument("--limit", type=int, help="Optional row limit.")
    parser.add_argument(
        "--output-path",
        default=str(
            resolve_entity_resolution_paths().predictions_dir / "rule_baseline_predictions.parquet"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run:
        print(
            {
                "output_path": args.output_path,
                "allow_empty": args.allow_empty,
                "limit": args.limit,
            }
        )
        return 0

    ensure_er_inputs(allow_empty=args.allow_empty, allow_missing_artifacts=True)
    frame = build_training_frame(
        load_candidate_pairs_frame(limit=args.limit),
        load_feature_base_frame(limit=args.limit),
        load_source_games_frame(limit=args.limit),
    )
    if frame.is_empty() and not args.allow_empty:
        raise RuntimeError("Rule baseline input is empty. Run `make ml-ready-data` first.")

    predictions = build_rule_predictions(frame)
    write_parquet(Path(args.output_path), predictions.to_dicts())
    print({"output_path": args.output_path, "prediction_count": predictions.height})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
