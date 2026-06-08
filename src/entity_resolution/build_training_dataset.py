"""Build an initial supervised-style ER training dataset from weak labels and safe negatives."""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

from src.entity_resolution.io import (
    ensure_er_inputs,
    feature_columns,
    load_candidate_pairs_frame,
    load_entity_resolution_config,
    load_feature_base_frame,
    load_reviewed_manual_labels_frame,
    load_source_games_frame,
    resolve_entity_resolution_paths,
)
from src.preprocessing.export_ml_ready_base import write_parquet


def valid_training_name_expr(column_name: str) -> pl.Expr:
    stripped = pl.col(column_name).str.strip_chars()
    return (
        pl.col(column_name).is_not_null()
        & (stripped.str.len_chars() > 2)
        & (~stripped.str.contains(r"^Q[0-9]+$"))
        & (~stripped.str.contains(r"^[0-9]+$"))
    )


def build_training_frame(
    candidate_pairs: pl.DataFrame,
    feature_base: pl.DataFrame,
    source_games: pl.DataFrame | None = None,
    manual_review_labels: pl.DataFrame | None = None,
) -> pl.DataFrame:
    joined = candidate_pairs.join(feature_base, on="pair_id", how="inner")
    if joined.is_empty():
        return joined

    if source_games is not None and not source_games.is_empty():
        left_context = source_games.select(
            [
                pl.col("source").alias("source_a"),
                pl.col("source_game_id").alias("source_id_a"),
                pl.col("name").alias("name_a"),
                pl.col("release_year").alias("release_year_a"),
            ]
        )
        right_context = source_games.select(
            [
                pl.col("source").alias("source_b"),
                pl.col("source_game_id").alias("source_id_b"),
                pl.col("name").alias("name_b"),
                pl.col("release_year").alias("release_year_b"),
            ]
        )
        joined = joined.join(left_context, on=["source_a", "source_id_a"], how="left").join(
            right_context, on=["source_b", "source_id_b"], how="left"
        )
        joined = joined.filter(
            valid_training_name_expr("name_a") & valid_training_name_expr("name_b")
        )
        if joined.is_empty():
            return joined

    if manual_review_labels is not None and not manual_review_labels.is_empty():
        labels = manual_review_labels.select(["pair_id", "manual_label"]).unique("pair_id")
        joined = joined.join(labels, on="pair_id", how="left")
    else:
        joined = joined.with_columns(pl.lit(None, dtype=pl.Int64).alias("manual_label"))

    config = load_entity_resolution_config()
    positive_sources = {
        str(source_name) for source_name in config.get("labels", {}).get("positive_sources", [])
    }
    negatives_cfg = config.get("labels", {}).get("synthetic_negative", {})
    negative_ratio = int(negatives_cfg.get("max_ratio_to_positive", 3))

    joined = joined.with_columns(
        [
            pl.when(pl.col("manual_label").is_not_null())
            .then(pl.col("manual_label"))
            .when(
                (pl.col("label_value") == "1")
                | pl.col("label_source").is_in(list(positive_sources))
                | pl.col("external_id_exact_match").fill_null(False)
            )
            .then(pl.lit(1))
            .otherwise(pl.lit(None))
            .alias("label"),
            pl.when(pl.col("manual_label").is_not_null())
            .then(pl.lit("manual_review"))
            .when(
                (pl.col("label_value") == "1")
                | pl.col("label_source").is_in(list(positive_sources))
                | pl.col("external_id_exact_match").fill_null(False)
            )
            .then(pl.lit("weak_positive"))
            .otherwise(pl.lit(None, dtype=pl.Utf8))
            .alias("training_label_source"),
            pl.lit(None, dtype=pl.Utf8).alias("synthetic_negative_rule"),
        ]
    )

    negative_condition_same_name_far_year = (
        pl.col("label").is_null()
        & (pl.col("name_similarity").fill_null(0.0) >= 0.9)
        & (pl.col("release_year_diff").fill_null(0) >= 10)
        & (~pl.col("external_id_exact_match").fill_null(False))
    )
    negative_condition_different_external_ids = (
        pl.col("label").is_null()
        & (~pl.col("external_id_exact_match").fill_null(False))
        & (pl.col("source_count_signal").fill_null(0) >= 2)
        & (pl.col("name_similarity").fill_null(0.0) <= 0.6)
        & (pl.col("release_year_diff").fill_null(0) >= 2)
    )
    negative_condition_low_name_diff_year = (
        pl.col("label").is_null()
        & (pl.col("name_similarity").fill_null(0.0) < 0.35)
        & (pl.col("release_year_diff").fill_null(0) >= 2)
    )

    joined = joined.with_columns(
        [
            pl.when(negative_condition_same_name_far_year)
            .then(pl.lit(0))
            .when(negative_condition_different_external_ids)
            .then(pl.lit(0))
            .when(negative_condition_low_name_diff_year)
            .then(pl.lit(0))
            .otherwise(pl.col("label"))
            .alias("label"),
            pl.when(negative_condition_same_name_far_year)
            .then(pl.lit("synthetic_negative"))
            .when(negative_condition_different_external_ids)
            .then(pl.lit("synthetic_negative"))
            .when(negative_condition_low_name_diff_year)
            .then(pl.lit("synthetic_negative"))
            .otherwise(pl.col("training_label_source"))
            .alias("training_label_source"),
            pl.when(negative_condition_same_name_far_year)
            .then(pl.lit("same_or_similar_name_different_release_year"))
            .when(negative_condition_different_external_ids)
            .then(pl.lit("different_external_ids"))
            .when(negative_condition_low_name_diff_year)
            .then(pl.lit("low_name_similarity_different_year"))
            .otherwise(pl.col("synthetic_negative_rule"))
            .alias("synthetic_negative_rule"),
        ]
    )

    positive_count = joined.filter(pl.col("label") == 1).height
    negative_cap = max(positive_count * negative_ratio, 0)
    negatives = joined.filter(pl.col("label") == 0)
    if positive_count == 0:
        negative_cap = negatives.height
    if negative_cap:
        negatives = negatives.head(negative_cap)
    positives = joined.filter(pl.col("label") == 1)

    labeled_parts = [frame for frame in (positives, negatives) if not frame.is_empty()]
    labeled = pl.concat(labeled_parts, how="vertical") if labeled_parts else joined.head(0)
    if labeled.is_empty():
        return labeled

    min_feature_count = 3
    availability_exprs = [
        pl.col(column_name).is_not_null().cast(pl.Int64) for column_name in feature_columns()
    ]
    labeled = labeled.with_columns(
        pl.sum_horizontal(availability_exprs).alias("available_feature_count")
    ).filter(pl.col("available_feature_count") >= min_feature_count)

    return labeled.sort(["label", "candidate_source", "pair_id"], descending=[True, False, False])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build ER baseline training dataset.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview training dataset paths only.",
    )
    parser.add_argument("--allow-empty", action="store_true", help="Allow empty dataset state.")
    parser.add_argument("--limit", type=int, help="Optional row limit.")
    parser.add_argument(
        "--output-path",
        default=str(resolve_entity_resolution_paths().predictions_dir / "training_dataset.parquet"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run:
        print(
            {
                "candidate_pairs_path": str(resolve_entity_resolution_paths().candidate_pairs_path),
                "feature_base_path": str(resolve_entity_resolution_paths().feature_base_path),
                "output_path": args.output_path,
                "allow_empty": args.allow_empty,
                "limit": args.limit,
            }
        )
        return 0

    ensure_er_inputs(allow_empty=args.allow_empty, allow_missing_artifacts=True)
    candidate_pairs = load_candidate_pairs_frame(limit=args.limit)
    feature_base = load_feature_base_frame(limit=args.limit)
    source_games = load_source_games_frame(limit=args.limit)
    training_frame = build_training_frame(
        candidate_pairs,
        feature_base,
        source_games,
        load_reviewed_manual_labels_frame(limit=args.limit),
    )
    if training_frame.is_empty() and not args.allow_empty:
        raise RuntimeError(
            "Training dataset is empty. Run `make rawg-demo`, `make wikidata-by-rawg`, "
            "`make wikidata-staging`, "
            "`make match-external-ids`, `make staging`, and `make ml-ready-data` first."
        )

    output_path = Path(args.output_path)
    write_parquet(output_path, training_frame.to_dicts())
    print(
        {
            "output_path": str(output_path),
            "training_row_count": training_frame.height,
            "positive_label_count": training_frame.filter(pl.col("label") == 1).height,
            "negative_label_count": training_frame.filter(pl.col("label") == 0).height,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
