"""Export ER training readiness and presentation notebook artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import polars as pl

from src.entity_resolution.io import ensure_output_directories
from src.ingestion.repository import IngestionRepository
from src.utils.config import project_root


def normalize(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def normalized_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: normalize(value) for key, value in row.items()} for row in rows]


def fetch_rows(repository: IngestionRepository, query: str) -> list[dict[str, Any]]:
    with repository.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            return normalized_rows(list(cursor.fetchall()))


def count_from_rows(rows: list[dict[str, Any]], key: str) -> int:
    if not rows:
        return 0
    return int(rows[0].get(key) or 0)


def collect_database_stats(repository: IngestionRepository) -> dict[str, Any]:
    status_counts = fetch_rows(
        repository,
        """
        SELECT
            review_status,
            review_label,
            COUNT(*) AS row_count
        FROM ml.entity_resolution_manual_reviews
        GROUP BY review_status, review_label
        ORDER BY review_status, review_label
        """,
    )
    by_strategy = fetch_rows(
        repository,
        """
        SELECT
            selection_strategy,
            review_status,
            review_label,
            COUNT(*) AS row_count
        FROM ml.entity_resolution_manual_reviews
        GROUP BY selection_strategy, review_status, review_label
        ORDER BY selection_strategy, review_status, review_label
        """,
    )
    by_reviewer = fetch_rows(
        repository,
        """
        SELECT
            COALESCE(reviewer, 'unknown') AS reviewer,
            review_status,
            review_label,
            COUNT(*) AS row_count
        FROM ml.entity_resolution_manual_reviews
        GROUP BY reviewer, review_status, review_label
        ORDER BY reviewer, review_status, review_label
        """,
    )
    invalid_rows = fetch_rows(
        repository,
        """
        SELECT COUNT(*) AS row_count
        FROM ml.v_entity_resolution_review_candidates
        WHERE review_status = 'reviewed'
          AND (
              name_a IS NULL OR name_b IS NULL
              OR name_a ~ '^Q[0-9]+$'
              OR name_b ~ '^Q[0-9]+$'
              OR name_a ~ '^[0-9]+$'
              OR name_b ~ '^[0-9]+$'
              OR length(btrim(name_a)) <= 2
              OR length(btrim(name_b)) <= 2
          )
        """,
    )
    candidate_counts = fetch_rows(
        repository,
        """
        SELECT
            candidate_source,
            COUNT(*) AS row_count
        FROM ml.entity_candidate_pairs
        GROUP BY candidate_source
        ORDER BY candidate_source
        """,
    )
    source_counts = fetch_rows(
        repository,
        """
        SELECT
            source,
            COUNT(*) AS row_count
        FROM stg.source_games
        GROUP BY source
        ORDER BY source
        """,
    )
    return {
        "manual_review_status_counts": status_counts,
        "manual_review_by_strategy": by_strategy,
        "manual_review_by_reviewer": by_reviewer,
        "invalid_reviewed_display_name_count": count_from_rows(invalid_rows, "row_count"),
        "candidate_pair_counts": candidate_counts,
        "source_game_counts": source_counts,
    }


def collect_training_dataset_stats(training_dataset_path: Path) -> dict[str, Any]:
    if not training_dataset_path.exists():
        return {"exists": False, "path": str(training_dataset_path)}

    frame = pl.read_parquet(training_dataset_path)
    label_counts = frame.group_by("label").len().sort("label").to_dicts()
    label_source_counts = (
        frame.group_by(["training_label_source", "label"])
        .len()
        .sort(["training_label_source", "label"])
        .to_dicts()
        if "training_label_source" in frame.columns
        else []
    )
    feature_stats = []
    if "available_feature_count" in frame.columns:
        feature_stats = frame.select(
            [
                pl.col("available_feature_count").min().alias("min_available_feature_count"),
                pl.col("available_feature_count").mean().alias("avg_available_feature_count"),
                pl.col("available_feature_count").max().alias("max_available_feature_count"),
            ]
        ).to_dicts()
    positive_count = int(frame.filter(pl.col("label") == 1).height)
    negative_count = int(frame.filter(pl.col("label") == 0).height)
    return {
        "exists": True,
        "path": str(training_dataset_path),
        "row_count": frame.height,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "positive_rate": round(positive_count / max(frame.height, 1), 6),
        "label_counts": label_counts,
        "label_source_counts": label_source_counts,
        "feature_availability": feature_stats,
    }


def load_model_metrics(metrics_path: Path) -> dict[str, Any]:
    if not metrics_path.exists():
        return {"exists": False, "path": str(metrics_path)}
    return {
        "exists": True,
        "path": str(metrics_path),
        "metrics": json.loads(metrics_path.read_text(encoding="utf-8")),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_notebook(path: Path, report_paths: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    notebook = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# Entity Resolution Training Report\n",
                    "\n",
                    "Notebook for the final presentation: manual review cleanup, pre-training ",
                    "readiness, model training, and post-training metrics.\n",
                ],
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## Required Presentation Metrics\n",
                    "\n",
                    "- Manual review coverage: reviewed/skipped/pending counts.\n",
                    "- Class balance: positive/negative counts and positive rate.\n",
                    "- Data quality: invalid display-name count and skipped invalid rows.\n",
                    "- Training set composition: manual labels vs weak labels ",
                    "vs synthetic negatives.\n",
                    "- Baseline model metrics: precision, recall, F1, ROC-AUC, PR-AUC.\n",
                    "- Manual-only validation metrics: same metrics on human-reviewed test rows.\n",
                    "- Decision distribution: auto_merge/manual_review/no_merge ",
                    "rates after prediction.\n",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "import json\n",
                    "from pathlib import Path\n",
                    "\n",
                    f"pre_path = Path({report_paths['pre_stats']!r})\n",
                    f"post_path = Path({report_paths['post_stats']!r})\n",
                    "pre = json.loads(pre_path.read_text()) if pre_path.exists() else None\n",
                    "post = json.loads(post_path.read_text()) if post_path.exists() else None\n",
                    "pre, post\n",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "def show_manual_counts(report):\n",
                    "    return report['database']['manual_review_status_counts']\n",
                    "\n",
                    "show_manual_counts(pre) if pre else None\n",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "post['model_metrics']['metrics'] if post and "
                    "post['model_metrics']['exists'] else None\n",
                ],
            },
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path.write_text(json.dumps(notebook, indent=2) + "\n", encoding="utf-8")


def export_training_report(*, phase: str) -> dict[str, Any]:
    paths = ensure_output_directories()
    repository = IngestionRepository()
    training_dataset_path = paths.predictions_dir / "training_dataset.parquet"
    metrics_path = paths.reports_dir / "metrics.json"
    report = {
        "phase": phase,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": collect_database_stats(repository),
        "training_dataset": collect_training_dataset_stats(training_dataset_path),
        "model_metrics": (
            load_model_metrics(metrics_path)
            if phase == "post"
            else {"exists": False, "path": str(metrics_path), "reason": "pre-training phase"}
        ),
    }

    stats_path = paths.reports_dir / f"{phase}_training_report_stats.json"
    strategy_csv_path = paths.reports_dir / f"{phase}_manual_review_by_strategy.csv"
    reviewer_csv_path = paths.reports_dir / f"{phase}_manual_review_by_reviewer.csv"
    notebook_path = project_root() / "notebooks" / "entity_resolution_training_report.ipynb"
    stats_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(strategy_csv_path, report["database"]["manual_review_by_strategy"])
    write_csv(reviewer_csv_path, report["database"]["manual_review_by_reviewer"])
    write_notebook(
        notebook_path,
        {
            "pre_stats": str(paths.reports_dir / "pre_training_report_stats.json"),
            "post_stats": str(paths.reports_dir / "post_training_report_stats.json"),
        },
    )
    return {
        "phase": phase,
        "stats_path": str(stats_path),
        "strategy_csv_path": str(strategy_csv_path),
        "reviewer_csv_path": str(reviewer_csv_path),
        "notebook_path": str(notebook_path),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export ER training report artifacts.")
    parser.add_argument(
        "--phase",
        choices=["pre", "post"],
        default="pre",
        help="Report phase marker.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(export_training_report(phase=args.phase))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
