"""Build a prioritized manual review queue from ER predictions."""

from __future__ import annotations

import argparse

import polars as pl

from src.entity_resolution.io import ensure_output_directories


def build_review_queue(frame: pl.DataFrame) -> pl.DataFrame:
    if frame.is_empty():
        return frame
    prioritized = (
        frame.with_columns(
            [
                (pl.col("same_game_probability") - 0.825).abs().alias("borderline_distance"),
                pl.when(pl.col("decision") == "manual_review")
                .then(0)
                .otherwise(1)
                .alias("decision_priority"),
            ]
        )
        .sort(["decision_priority", "borderline_distance", "same_game_probability"])
        .select(
            [
                "source_a",
                "source_id_a",
                "name_a",
                "release_year_a",
                "source_b",
                "source_id_b",
                "name_b",
                "release_year_b",
                "same_game_probability",
                "decision",
                "explanation_factors_json",
                "candidate_source",
                "label_source",
            ]
        )
    )
    return prioritized


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build ER manual review queue.")
    parser.add_argument("--dry-run", action="store_true", help="Preview queue output paths only.")
    parser.add_argument("--allow-empty", action="store_true", help="Allow empty predictions.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = ensure_output_directories()
    predictions_path = paths.predictions_dir / "predictions.parquet"
    queue_path = paths.predictions_dir / "manual_review_queue.parquet"
    report_path = paths.reports_dir / "manual_review_queue.csv"
    if args.dry_run:
        print(
            {
                "predictions_path": str(predictions_path),
                "queue_path": str(queue_path),
                "report_path": str(report_path),
            }
        )
        return 0

    if not predictions_path.exists():
        if args.allow_empty:
            print({"manual_review_queue_count": 0, "skipped": True})
            return 0
        raise RuntimeError("Predictions artifact missing. Run `make er-predict` first.")

    queue = build_review_queue(pl.read_parquet(predictions_path))
    queue.write_parquet(queue_path)
    queue.write_csv(report_path)
    print({"manual_review_queue_count": queue.height, "queue_path": str(queue_path)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
