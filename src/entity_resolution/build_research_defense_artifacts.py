"""Build research artifacts for the ML defense report."""

from __future__ import annotations

import argparse
import csv
import json
import warnings
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import polars as pl
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from src.entity_resolution.build_training_dataset import build_training_frame
from src.entity_resolution.io import (
    ensure_output_directories,
    feature_columns,
    load_candidate_pairs_frame,
    load_entity_resolution_config,
    load_feature_base_frame,
    load_reviewed_manual_labels_frame,
    load_source_games_frame,
)
from src.entity_resolution.train_baseline_model import (
    compute_metrics,
    label_source_counts,
    sample_weights_for_rows,
)
from src.ingestion.repository import IngestionRepository
from src.utils.config import project_root

DEFAULT_ARTIFACT_DIR = project_root() / "data" / "artifacts" / "reports" / "ml_research_defense"
DEFAULT_MODEL_WEIGHT_POLICY = {
    "manual_review": 1.0,
    "weak_positive": 0.05,
    "synthetic_negative": 0.5,
}
FEATURE_GROUPS = {
    "name": {"name_similarity", "alias_similarity"},
    "year": {"release_year_diff"},
    "external_id": {"external_id_exact_match"},
    "companies": {"developer_overlap", "publisher_overlap"},
    "taxonomy": {"platform_jaccard", "genre_jaccard", "tag_jaccard"},
    "description": {"description_available_flag", "description_language_match"},
    "source_signal": {"source_count_signal"},
}


def round_or_none(value: float | None, digits: int = 6) -> float | None:
    return round(float(value), digits) if value is not None else None


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_jsonable(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def to_jsonable(value: object) -> object:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [to_jsonable(item) for item in value]
    return value


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fetch_rows(repository: IngestionRepository, query: str) -> list[dict[str, Any]]:
    with repository.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            return list(cursor.fetchall())


def fetch_baseline_counts(repository: IngestionRepository) -> dict[str, Any]:
    return {
        "source_games_by_source": fetch_rows(
            repository,
            """
            SELECT source, COUNT(*) AS row_count
            FROM stg.source_games
            GROUP BY source
            ORDER BY source
            """,
        ),
        "candidate_pairs_by_source": fetch_rows(
            repository,
            """
            SELECT candidate_source, COUNT(*) AS row_count
            FROM ml.entity_candidate_pairs
            GROUP BY candidate_source
            ORDER BY candidate_source
            """,
        ),
        "manual_review_labels": fetch_rows(
            repository,
            """
            SELECT review_status, review_label, COUNT(*) AS row_count
            FROM ml.entity_resolution_manual_reviews
            GROUP BY review_status, review_label
            ORDER BY review_status, review_label
            """,
        ),
        "model_decisions": fetch_rows(
            repository,
            """
            SELECT decision, COUNT(*) AS row_count
            FROM ml.entity_resolution_predictions
            GROUP BY decision
            ORDER BY decision
            """,
        ),
        "dm_counts": fetch_rows(
            repository,
            """
            SELECT 'canonical_games' AS object_name, COUNT(*) AS row_count
            FROM dm.canonical_games
            UNION ALL
            SELECT 'canonical_game_sources', COUNT(*) FROM dm.canonical_game_sources
            UNION ALL
            SELECT 'game_recommendations', COUNT(*) FROM dm.game_recommendations
            ORDER BY object_name
            """,
        ),
    }


def load_training_frame() -> pl.DataFrame:
    return build_training_frame(
        load_candidate_pairs_frame(),
        load_feature_base_frame(),
        load_source_games_frame(),
        load_reviewed_manual_labels_frame(),
    )


def selected_feature_names(excluded_features: set[str]) -> list[str]:
    return [name for name in feature_columns() if name not in excluded_features]


def train_and_score(
    training_frame: pl.DataFrame,
    *,
    selected_features: list[str],
    random_state: int,
    weight_policy: dict[str, float],
) -> dict[str, Any]:
    prepared = training_frame.with_columns(
        [
            pl.col(column_name).cast(pl.Float64, strict=False).alias(column_name)
            for column_name in selected_features
        ]
    )
    X = prepared.select(selected_features).to_numpy().tolist()
    y = prepared["label"].cast(pl.Int64).to_list()
    X_train, X_test, y_train, y_test, train_rows, test_rows = train_test_split(
        X,
        y,
        prepared.to_dicts(),
        test_size=0.4,
        random_state=random_state,
        stratify=y if len(set(y)) > 1 else None,
    )
    pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=random_state,
                ),
            ),
        ]
    )
    train_sample_weights = sample_weights_for_rows(
        train_rows,
        manual_label_weight=weight_policy["manual_review"],
        weak_positive_weight=weight_policy["weak_positive"],
        synthetic_negative_weight=weight_policy["synthetic_negative"],
    )
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Skipping features without any observed values",
            category=UserWarning,
        )
        pipeline.fit(X_train, y_train, model__sample_weight=train_sample_weights)
        y_prob = [float(value) for value in pipeline.predict_proba(X_test)[:, 1].tolist()]
    y_pred = [1 if probability >= 0.5 else 0 for probability in y_prob]
    return {
        "pipeline": pipeline,
        "metrics": compute_metrics(y_test, y_pred, y_prob),
        "test_rows": test_rows,
        "y_true": y_test,
        "y_prob": y_prob,
        "selected_features": selected_features,
    }


def build_ablation_rows(training_frame: pl.DataFrame) -> list[dict[str, object]]:
    config = load_entity_resolution_config()
    random_state = int(
        config.get("model", {}).get("logistic_regression", {}).get("random_state", 42)
    )
    rows: list[dict[str, object]] = []
    scenarios: list[tuple[str, set[str]]] = [("all_features", set())]
    scenarios.extend(
        (f"without_{group_name}", set(group_features))
        for group_name, group_features in FEATURE_GROUPS.items()
    )
    for scenario_name, excluded_features in scenarios:
        selected_features = selected_feature_names(excluded_features)
        result = train_and_score(
            training_frame,
            selected_features=selected_features,
            random_state=random_state,
            weight_policy=DEFAULT_MODEL_WEIGHT_POLICY,
        )
        metrics = result["metrics"]
        rows.append(
            {
                "scenario": scenario_name,
                "feature_count": len(selected_features),
                "excluded_features": ", ".join(sorted(excluded_features)),
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
                "roc_auc": metrics["roc_auc"],
                "pr_auc": metrics["pr_auc"],
                "confusion_matrix": json.dumps(metrics["confusion_matrix"]),
            }
        )
    return rows


def build_calibration_report(training_frame: pl.DataFrame) -> dict[str, Any]:
    config = load_entity_resolution_config()
    random_state = int(
        config.get("model", {}).get("logistic_regression", {}).get("random_state", 42)
    )
    result = train_and_score(
        training_frame,
        selected_features=feature_columns(),
        random_state=random_state,
        weight_policy=DEFAULT_MODEL_WEIGHT_POLICY,
    )
    y_true = [int(value) for value in result["y_true"]]
    y_prob = [float(value) for value in result["y_prob"]]
    bins: list[dict[str, object]] = []
    for index in range(10):
        lower = index / 10
        upper = (index + 1) / 10
        selected = [
            (truth, probability)
            for truth, probability in zip(y_true, y_prob, strict=False)
            if lower <= probability < upper or (index == 9 and probability == 1.0)
        ]
        probabilities = [probability for _truth, probability in selected]
        labels = [truth for truth, _probability in selected]
        bins.append(
            {
                "bin": f"{lower:.1f}-{upper:.1f}",
                "count": len(selected),
                "avg_probability": round_or_none(
                    sum(probabilities) / len(probabilities) if probabilities else None
                ),
                "positive_rate": round_or_none(sum(labels) / len(labels) if labels else None),
            }
        )
    probability_distribution: list[dict[str, object]] = []
    by_label: dict[int, list[float]] = defaultdict(list)
    for truth, probability in zip(y_true, y_prob, strict=False):
        by_label[int(truth)].append(probability)
    for label, values in sorted(by_label.items()):
        probability_distribution.append(
            {
                "label": label,
                "count": len(values),
                "min": round_or_none(min(values) if values else None),
                "p10": round_or_none(quantile(values, 0.10)),
                "median": round_or_none(quantile(values, 0.50)),
                "p90": round_or_none(quantile(values, 0.90)),
                "max": round_or_none(max(values) if values else None),
            }
        )
    return {
        "brier_score": round_or_none(brier_score_loss(y_true, y_prob)),
        "bins": bins,
        "probability_distribution": probability_distribution,
        "sample_weight_policy": DEFAULT_MODEL_WEIGHT_POLICY,
    }


def fetch_active_learning_candidates(repository: IngestionRepository) -> list[dict[str, Any]]:
    return fetch_rows(
        repository,
        """
        WITH candidates AS (
            SELECT
                pair_id::TEXT AS pair_id,
                source_a,
                source_id_a,
                name_a,
                release_year_a,
                source_b,
                source_id_b,
                name_b,
                release_year_b,
                candidate_source,
                same_game_probability,
                name_similarity,
                release_year_diff,
                review_status,
                review_label,
                CASE
                    WHEN review_status = 'reviewed' THEN 'already_reviewed'
                    WHEN same_game_probability BETWEEN 0.45 AND 0.55 THEN 'high_uncertainty'
                    WHEN same_game_probability >= 0.90 THEN 'high_risk_model_positive'
                    WHEN same_game_probability >= 0.70 THEN 'manual_review_priority'
                    ELSE 'low_priority'
                END AS active_learning_bucket
            FROM ml.v_entity_resolution_review_candidates
            WHERE review_status IS NULL
               OR review_status IN ('pending', 'unsure', 'skipped')
        )
        SELECT *
        FROM candidates
        WHERE active_learning_bucket <> 'low_priority'
        ORDER BY
            CASE active_learning_bucket
                WHEN 'high_uncertainty' THEN 0
                WHEN 'high_risk_model_positive' THEN 1
                WHEN 'manual_review_priority' THEN 2
                ELSE 3
            END,
            ABS(COALESCE(same_game_probability, 0.5) - 0.5),
            same_game_probability DESC NULLS LAST
        LIMIT 250
        """,
    )


def fetch_defense_demo_cases(repository: IngestionRepository) -> list[dict[str, Any]]:
    er_cases = fetch_rows(
        repository,
        """
        (
            SELECT
                'successful_merge' AS case_type,
                name_a AS item_a,
                name_b AS item_b,
                same_game_probability AS score,
                'High-confidence reviewed positive ER pair' AS interpretation
            FROM ml.v_entity_resolution_review_candidates
            WHERE review_status = 'reviewed'
              AND review_label IS TRUE
            ORDER BY same_game_probability DESC NULLS LAST
            LIMIT 3
        )
        UNION ALL
        (
            SELECT
                'rejected_risky_match' AS case_type,
                name_a AS item_a,
                name_b AS item_b,
                same_game_probability AS score,
                'Reviewed negative: similar title but different game/entity' AS interpretation
            FROM ml.v_entity_resolution_review_candidates
            WHERE review_status = 'reviewed'
              AND review_label IS FALSE
            ORDER BY same_game_probability DESC NULLS LAST
            LIMIT 3
        )
        UNION ALL
        (
            SELECT
                'active_learning_candidate' AS case_type,
                name_a AS item_a,
                name_b AS item_b,
                same_game_probability AS score,
                'Unlabeled high-uncertainty pair for the next manual-review batch'
                    AS interpretation
            FROM ml.v_entity_resolution_review_candidates
            WHERE review_status IS NULL
               OR review_status IN ('pending', 'unsure', 'skipped')
            ORDER BY ABS(COALESCE(same_game_probability, 0.5) - 0.5),
                     same_game_probability DESC NULLS LAST
            LIMIT 3
        )
        ORDER BY case_type, score DESC NULLS LAST
        """,
    )
    recommendation_cases = fetch_rows(
        repository,
        """
        SELECT
            'recommendation_example' AS case_type,
            seed.canonical_name AS item_a,
            rec.canonical_name AS item_b,
            r.score,
            'Content-based recommendation with 3+ shared explanation features'
                AS interpretation
        FROM dm.game_recommendations r
        JOIN dm.canonical_games seed
            ON seed.canonical_game_id = r.canonical_game_id
        JOIN dm.canonical_games rec
            ON rec.canonical_game_id = r.recommended_canonical_game_id
        WHERE jsonb_array_length(r.explanation_factors_json->'shared_features') >= 3
          AND seed.canonical_name !~ '^Q[0-9]+$'
          AND rec.canonical_name !~ '^Q[0-9]+$'
        ORDER BY r.score DESC, seed.canonical_name, rec.canonical_name
        LIMIT 5
        """,
    )
    return er_cases + recommendation_cases


def fetch_recommendation_examples(repository: IngestionRepository) -> dict[str, Any]:
    coverage = fetch_rows(
        repository,
        """
        SELECT
            COUNT(*) AS recommendation_rows,
            COUNT(DISTINCT canonical_game_id) AS games_with_recommendations,
            MIN(score) AS min_score,
            ROUND(AVG(score)::NUMERIC, 6) AS avg_score,
            MAX(score) AS max_score
        FROM dm.game_recommendations
        """,
    )
    examples = fetch_rows(
        repository,
        """
        SELECT
            seed.canonical_name AS seed_game,
            rec_game.canonical_name AS recommended_game,
            r.rank,
            r.score,
            r.explanation_factors_json::TEXT AS explanation_factors_json
        FROM dm.game_recommendations r
        JOIN dm.canonical_games seed
            ON seed.canonical_game_id = r.canonical_game_id
        JOIN dm.canonical_games rec_game
            ON rec_game.canonical_game_id = r.recommended_canonical_game_id
        WHERE jsonb_array_length(r.explanation_factors_json->'shared_features') >= 3
          AND seed.canonical_name !~ '^Q[0-9]+$'
          AND rec_game.canonical_name !~ '^Q[0-9]+$'
        ORDER BY r.score DESC, seed.canonical_name, r.rank
        LIMIT 25
        """,
    )
    score_distribution = fetch_rows(
        repository,
        """
        SELECT
            CASE
                WHEN score >= 1.0 THEN '1.0'
                ELSE CONCAT(
                    ROUND((FLOOR(score * 10) / 10)::NUMERIC, 1),
                    '-',
                    ROUND(((FLOOR(score * 10) + 1) / 10)::NUMERIC, 1)
                )
            END AS score_bucket,
            COUNT(*) AS row_count
        FROM dm.game_recommendations
        GROUP BY score_bucket
        ORDER BY score_bucket
        """,
    )
    return {"coverage": coverage, "examples": examples, "score_distribution": score_distribution}


def read_optional_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_preview(path: Path, limit: int = 20) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as file:
        return [row for index, row in enumerate(csv.DictReader(file)) if index < limit]


def load_existing_er_artifacts() -> dict[str, Any]:
    root = project_root() / "data" / "artifacts" / "reports" / "entity_resolution"
    iterations = root / "iterations"
    merge = root / "merge_strategies"
    return {
        "current_metrics": read_optional_json(root / "metrics.json"),
        "v3c_metrics": read_optional_json(iterations / "metrics_v3c_weak005.json"),
        "merge_strategy_comparison": read_optional_json(merge / "merge_strategy_comparison.json"),
        "post_training_report_v3c": read_optional_json(
            iterations / "post_training_report_v3c_weak005.json"
        ),
    }


def load_data_quality_artifacts() -> dict[str, Any]:
    root = project_root() / "data" / "artifacts" / "reports"
    return {
        "dq_summary": read_optional_json(root / "dq_summary.json"),
        "field_completeness_preview": read_csv_preview(root / "field_completeness_by_source.csv"),
        "conflict_preview": read_csv_preview(root / "conflict_report.csv"),
        "anomaly_preview": read_csv_preview(root / "anomaly_report.csv"),
        "note": (
            "DQ artifacts reflect the latest data-quality run. Run `make data-quality` "
            "before final defense if the source corpus has changed."
        ),
    }


def write_markdown_summary(path: Path, summary: dict[str, Any]) -> None:
    baseline = summary["baseline_counts"]
    ablation_rows = summary["ablation_study"]
    calibration = summary["calibration"]
    recommendations = summary["recommendations"]
    defense_demo_case_count = summary["defense_demo_case_count"]
    data_quality = summary["data_quality"]
    lines = [
        "# ML Research Defense Runtime Summary",
        "",
        "This generated report summarizes the current defense-ready ML artifacts.",
        "",
        "## Baseline Counts",
        "",
        f"- Sources: `{baseline['source_games_by_source']}`",
        f"- Candidate pairs: `{baseline['candidate_pairs_by_source']}`",
        f"- Manual labels: `{baseline['manual_review_labels']}`",
        f"- Model decisions: `{baseline['model_decisions']}`",
        f"- DM counts: `{baseline['dm_counts']}`",
        "",
        "## Ablation Study",
        "",
        "| Scenario | Precision | Recall | F1 | ROC-AUC | PR-AUC |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in ablation_rows:
        lines.append(
            "| {scenario} | {precision} | {recall} | {f1} | {roc_auc} | {pr_auc} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Calibration",
            "",
            f"- Brier score: `{calibration['brier_score']}`",
            f"- Probability distribution: `{calibration['probability_distribution']}`",
            "",
            "## Recommendations",
            "",
            f"- Coverage: `{recommendations['coverage']}`",
            f"- Example rows: `{len(recommendations['examples'])}`",
            f"- Score distribution: `{recommendations['score_distribution']}`",
            f"- Defense demo cases: `{defense_demo_case_count}`",
            "",
            "## Data Quality Impact",
            "",
            f"- DQ note: `{data_quality['note']}`",
            "- Field completeness preview rows: "
            f"`{len(data_quality['field_completeness_preview'])}`",
            f"- Conflict preview rows: `{len(data_quality['conflict_preview'])}`",
            f"- Anomaly preview rows: `{len(data_quality['anomaly_preview'])}`",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_research_defense_artifacts(output_dir: Path) -> dict[str, Any]:
    repository = IngestionRepository()
    training_frame = load_training_frame()
    if training_frame.is_empty():
        raise RuntimeError("Training frame is empty; run ER/data-stage commands first.")

    baseline_counts = fetch_baseline_counts(repository)
    ablation_rows = build_ablation_rows(training_frame)
    calibration = build_calibration_report(training_frame)
    active_learning_candidates = fetch_active_learning_candidates(repository)
    recommendations = fetch_recommendation_examples(repository)
    defense_demo_cases = fetch_defense_demo_cases(repository)
    existing_er_artifacts = load_existing_er_artifacts()
    data_quality = load_data_quality_artifacts()
    summary = {
        "baseline_counts": baseline_counts,
        "training_dataset": {
            "row_count": training_frame.height,
            "positive_count": training_frame.filter(pl.col("label") == 1).height,
            "negative_count": training_frame.filter(pl.col("label") == 0).height,
            "label_source_counts": label_source_counts(training_frame),
        },
        "ablation_study": ablation_rows,
        "calibration": calibration,
        "active_learning_candidate_count": len(active_learning_candidates),
        "defense_demo_case_count": len(defense_demo_cases),
        "recommendations": recommendations,
        "existing_er_artifacts": existing_er_artifacts,
        "data_quality": data_quality,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "ml_research_defense_summary.json", summary)
    write_csv(output_dir / "ablation_study.csv", ablation_rows)
    write_csv(output_dir / "calibration_bins.csv", calibration["bins"])
    write_csv(
        output_dir / "probability_distribution.csv",
        calibration["probability_distribution"],
    )
    write_csv(output_dir / "active_learning_candidates.csv", active_learning_candidates)
    write_csv(output_dir / "defense_demo_cases.csv", defense_demo_cases)
    write_csv(output_dir / "recommendation_examples.csv", recommendations["examples"])
    write_csv(
        output_dir / "recommendation_score_distribution.csv",
        recommendations["score_distribution"],
    )
    write_markdown_summary(output_dir / "ml_research_defense_summary.md", summary)
    return {
        "output_dir": str(output_dir),
        "summary_json": str(output_dir / "ml_research_defense_summary.json"),
        "ablation_rows": len(ablation_rows),
        "active_learning_candidate_count": len(active_learning_candidates),
        "defense_demo_case_count": len(defense_demo_cases),
        "recommendation_example_count": len(recommendations["examples"]),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build ML research defense artifacts.")
    parser.add_argument("--output-dir", default=str(DEFAULT_ARTIFACT_DIR))
    return parser


def main(argv: list[str] | None = None) -> int:
    ensure_output_directories()
    args = build_parser().parse_args(argv)
    print(build_research_defense_artifacts(Path(args.output_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
