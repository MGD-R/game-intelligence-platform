"""Build lightweight title-embedding ER research artifacts.

This module intentionally avoids external model downloads. It uses local TF-IDF and
SVD vectors as a reproducible embedding-style baseline for the defense notebook.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, normalize

from src.entity_resolution.build_research_defense_artifacts import (
    horizontal_bar_chart_svg,
    write_csv,
    write_json,
    write_text,
)
from src.ingestion.repository import IngestionRepository
from src.utils.config import project_root

DEFAULT_OUTPUT_DIR = project_root() / "data" / "artifacts" / "reports" / "embedding_research"
RANDOM_STATE = 42

FEATURE_SETS: dict[str, list[str]] = {
    "name_similarity_only": ["name_similarity"],
    "char_tfidf_only": ["char_tfidf_cosine"],
    "word_tfidf_only": ["word_tfidf_cosine"],
    "svd_title_only": ["title_svd_cosine"],
    "embedding_stack": ["char_tfidf_cosine", "word_tfidf_cosine", "title_svd_cosine"],
    "combined_name_embedding_year": [
        "name_similarity",
        "char_tfidf_cosine",
        "word_tfidf_cosine",
        "title_svd_cosine",
        "release_year_abs_diff",
        "same_release_year",
    ],
}


def clean_text(value: object) -> str:
    return str(value or "").strip()


def nullable_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def pairwise_sparse_cosine(left_matrix: Any, right_matrix: Any) -> list[float]:
    values = left_matrix.multiply(right_matrix).sum(axis=1)
    return [float(value) for value in np.asarray(values).ravel()]


def pairwise_dense_cosine(left_matrix: np.ndarray, right_matrix: np.ndarray) -> list[float]:
    return [float(value) for value in np.sum(left_matrix * right_matrix, axis=1)]


def svd_component_count(document_count: int, feature_count: int, requested: int = 64) -> int:
    upper_bound = min(document_count, feature_count) - 1
    return max(0, min(requested, upper_bound))


def add_embedding_features(rows: list[dict[str, Any]]) -> list[dict[str, object]]:
    names_a = [clean_text(row.get("name_a")) for row in rows]
    names_b = [clean_text(row.get("name_b")) for row in rows]
    corpus = names_a + names_b

    char_vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), lowercase=True)
    char_matrix = char_vectorizer.fit_transform(corpus)
    char_left = char_matrix[: len(rows)]
    char_right = char_matrix[len(rows) :]
    char_scores = pairwise_sparse_cosine(char_left, char_right)

    word_vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        lowercase=True,
        token_pattern=r"(?u)\b\w+\b",
    )
    word_matrix = word_vectorizer.fit_transform(corpus)
    word_left = word_matrix[: len(rows)]
    word_right = word_matrix[len(rows) :]
    word_scores = pairwise_sparse_cosine(word_left, word_right)

    component_count = svd_component_count(word_matrix.shape[0], word_matrix.shape[1])
    if component_count:
        svd = TruncatedSVD(n_components=component_count, random_state=RANDOM_STATE)
        dense = normalize(svd.fit_transform(word_matrix))
        svd_scores = pairwise_dense_cosine(dense[: len(rows)], dense[len(rows) :])
    else:
        svd_scores = word_scores

    enriched_rows: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        year_diff = row.get("release_year_diff")
        year_diff_float = nullable_float(year_diff)
        enriched_rows.append(
            {
                **row,
                "manual_label": 1 if row.get("review_label") is True else 0,
                "char_tfidf_cosine": round(char_scores[index], 6),
                "word_tfidf_cosine": round(word_scores[index], 6),
                "title_svd_cosine": round(svd_scores[index], 6),
                "release_year_abs_diff": abs(year_diff_float)
                if year_diff_float is not None
                else None,
                "same_release_year": (
                    1 if year_diff_float == 0 else 0 if year_diff_float is not None else None
                ),
            }
        )
    return enriched_rows


def feature_matrix(rows: list[dict[str, object]], feature_names: list[str]) -> np.ndarray:
    return np.asarray(
        [[nullable_float(row.get(feature_name)) for feature_name in feature_names] for row in rows],
        dtype=float,
    )


def binary_metrics(
    y_true: np.ndarray, y_score: np.ndarray, threshold: float = 0.5
) -> dict[str, object]:
    y_pred = (y_score >= threshold).astype(int)
    return {
        "threshold": threshold,
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 6),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 6),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 6),
        "roc_auc": round(float(roc_auc_score(y_true, y_score)), 6)
        if len(set(y_true.tolist())) > 1
        else None,
        "pr_auc": round(float(average_precision_score(y_true, y_score)), 6),
        "brier_score": round(float(brier_score_loss(y_true, y_score)), 6),
        "positive_predictions": int(y_pred.sum()),
    }


def train_embedding_models(
    rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    labels = np.asarray([int(row["manual_label"]) for row in rows], dtype=int)
    indices = np.arange(len(rows))
    train_indices, test_indices = train_test_split(
        indices,
        test_size=0.30,
        random_state=RANDOM_STATE,
        stratify=labels,
    )

    comparison_rows: list[dict[str, object]] = []
    threshold_rows: list[dict[str, object]] = []
    scored_rows: list[dict[str, object]] = []

    for model_name, feature_names in FEATURE_SETS.items():
        x = feature_matrix(rows, feature_names)
        x_train = x[train_indices]
        x_test = x[test_indices]
        y_train = labels[train_indices]
        y_test = labels[test_indices]
        pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        class_weight="balanced",
                        max_iter=1000,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        )
        pipeline.fit(x_train, y_train)
        probabilities = pipeline.predict_proba(x_test)[:, 1]
        metrics = binary_metrics(y_test, probabilities)
        comparison_rows.append(
            {
                "model": model_name,
                "features": ", ".join(feature_names),
                "train_rows": len(train_indices),
                "test_rows": len(test_indices),
                "positive_test_rows": int(y_test.sum()),
                "negative_test_rows": int(len(y_test) - y_test.sum()),
                **metrics,
            }
        )
        if model_name == "combined_name_embedding_year":
            all_probabilities = pipeline.predict_proba(x)[:, 1]
            for threshold in (0.50, 0.70, 0.90, 0.95):
                threshold_rows.append(
                    {
                        "model": model_name,
                        **binary_metrics(y_test, probabilities, threshold=threshold),
                    }
                )
            for row, probability in zip(rows, all_probabilities, strict=True):
                scored_rows.append(
                    {
                        "pair_id": row.get("pair_id"),
                        "source_a": row.get("source_a"),
                        "source_id_a": row.get("source_id_a"),
                        "name_a": row.get("name_a"),
                        "release_year_a": row.get("release_year_a"),
                        "source_b": row.get("source_b"),
                        "source_id_b": row.get("source_id_b"),
                        "name_b": row.get("name_b"),
                        "release_year_b": row.get("release_year_b"),
                        "candidate_source": row.get("candidate_source"),
                        "manual_label": row.get("manual_label"),
                        "name_similarity": row.get("name_similarity"),
                        "char_tfidf_cosine": row.get("char_tfidf_cosine"),
                        "word_tfidf_cosine": row.get("word_tfidf_cosine"),
                        "title_svd_cosine": row.get("title_svd_cosine"),
                        "release_year_abs_diff": row.get("release_year_abs_diff"),
                        "embedding_same_game_probability": round(float(probability), 6),
                    }
                )

    comparison_rows.sort(key=lambda row: (-float(row["f1"]), str(row["model"])))
    scored_rows.sort(
        key=lambda row: (
            -float(row["embedding_same_game_probability"]),
            str(row["name_a"]).lower(),
            str(row["name_b"]).lower(),
        )
    )
    return comparison_rows, threshold_rows, scored_rows


def error_case_rows(
    scored_rows: list[dict[str, object]], limit: int = 50
) -> list[dict[str, object]]:
    false_positive_like = [
        {
            **row,
            "case_type": "reviewed_negative_high_embedding_probability",
        }
        for row in scored_rows
        if int(row["manual_label"]) == 0 and float(row["embedding_same_game_probability"]) >= 0.70
    ]
    false_negative_like = [
        {
            **row,
            "case_type": "reviewed_positive_low_embedding_probability",
        }
        for row in scored_rows
        if int(row["manual_label"]) == 1 and float(row["embedding_same_game_probability"]) < 0.50
    ]
    false_positive_like.sort(key=lambda row: -float(row["embedding_same_game_probability"]))
    false_negative_like.sort(key=lambda row: float(row["embedding_same_game_probability"]))
    return (false_positive_like[:limit] + false_negative_like[:limit])[: limit * 2]


def similarity_distribution_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    buckets: dict[str, int] = {f"{start / 10:.1f}-{(start + 1) / 10:.1f}": 0 for start in range(10)}
    buckets["1.0"] = 0
    for row in rows:
        score = float(row["char_tfidf_cosine"])
        if score >= 1.0:
            bucket = "1.0"
        else:
            bucket = f"{int(score * 10) / 10:.1f}-{(int(score * 10) + 1) / 10:.1f}"
        buckets[bucket] += 1
    return [
        {"char_tfidf_bucket": bucket, "pair_count": count}
        for bucket, count in buckets.items()
        if count
    ]


def fetch_reviewed_pair_rows(repository: IngestionRepository) -> list[dict[str, Any]]:
    with repository.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
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
                    name_similarity,
                    release_year_diff,
                    same_game_probability,
                    model_decision,
                    review_label,
                    review_status,
                    review_notes
                FROM ml.v_entity_resolution_review_candidates
                WHERE review_status = 'reviewed'
                  AND review_label IS NOT NULL
                  AND COALESCE(name_a, '') <> ''
                  AND COALESCE(name_b, '') <> ''
                  AND name_a !~ '^Q[0-9]+$'
                  AND name_b !~ '^Q[0-9]+$'
                ORDER BY pair_id
                """
            )
            return list(cursor.fetchall())


def write_markdown_summary(path: Path, summary: dict[str, object]) -> None:
    lines = [
        "# Lightweight Title Embedding ER Research",
        "",
        "This report uses local TF-IDF/SVD vectors as a reproducible embedding-style "
        "baseline. It does not download external neural models.",
        "",
        f"- Reviewed rows used: `{summary['reviewed_pair_count']}`",
        f"- Positive labels: `{summary['positive_label_count']}`",
        f"- Negative labels: `{summary['negative_label_count']}`",
        f"- Best model by F1: `{summary['best_model']}`",
        f"- Best F1: `{summary['best_f1']}`",
        f"- Error case rows: `{summary['error_case_count']}`",
        "",
        "Interpretation:",
        "",
        "- Title embeddings provide a reproducible comparison against fuzzy title features.",
        "- High-probability reviewed negatives are useful remaster/edition/franchise examples.",
        "- This is a research lane; it does not alter production canonical merges.",
        "",
    ]
    write_text(path, "\n".join(lines))


def build_embedding_research(output_dir: Path) -> dict[str, object]:
    repository = IngestionRepository()
    output_dir.mkdir(parents=True, exist_ok=True)
    reviewed_rows = fetch_reviewed_pair_rows(repository)
    enriched_rows = add_embedding_features(reviewed_rows)
    comparison_rows, threshold_rows, scored_rows = train_embedding_models(enriched_rows)
    error_rows = error_case_rows(scored_rows)
    distribution_rows = similarity_distribution_rows(enriched_rows)
    best_row = comparison_rows[0] if comparison_rows else {}
    summary = {
        "reviewed_pair_count": len(enriched_rows),
        "positive_label_count": sum(1 for row in enriched_rows if int(row["manual_label"]) == 1),
        "negative_label_count": sum(1 for row in enriched_rows if int(row["manual_label"]) == 0),
        "model_count": len(comparison_rows),
        "best_model": best_row.get("model"),
        "best_f1": best_row.get("f1"),
        "error_case_count": len(error_rows),
        "models": comparison_rows,
    }

    write_csv(output_dir / "embedding_model_comparison.csv", comparison_rows)
    write_csv(output_dir / "embedding_threshold_eval.csv", threshold_rows)
    write_csv(output_dir / "embedding_pair_scores.csv", scored_rows)
    write_csv(output_dir / "embedding_error_cases.csv", error_rows)
    write_csv(output_dir / "title_embedding_similarity_distribution.csv", distribution_rows)
    write_json(output_dir / "embedding_research_summary.json", summary)
    write_markdown_summary(output_dir / "embedding_research_summary.md", summary)
    write_text(
        output_dir / "embedding_model_f1.svg",
        horizontal_bar_chart_svg(
            comparison_rows,
            title="Lightweight Title Embedding ER: F1 By Model",
            label_key="model",
            value_key="f1",
            value_label="F1 score",
        ),
    )
    return {
        "output_dir": str(output_dir),
        "reviewed_pair_count": len(enriched_rows),
        "positive_label_count": summary["positive_label_count"],
        "negative_label_count": summary["negative_label_count"],
        "best_model": summary["best_model"],
        "best_f1": summary["best_f1"],
        "error_case_count": len(error_rows),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build lightweight title embedding ER artifacts.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(build_embedding_research(Path(args.output_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
