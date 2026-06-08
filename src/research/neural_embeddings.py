"""Optional neural title embedding research with a deterministic fallback."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.utils.config import project_root

DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_OUTPUT_DIR = project_root() / "data" / "artifacts" / "reports" / "neural_embeddings"


def cosine(left: np.ndarray, right: np.ndarray) -> float:
    left_norm = float(np.linalg.norm(left))
    right_norm = float(np.linalg.norm(right))
    if not left_norm or not right_norm:
        return 0.0
    return float(np.dot(left, right) / (left_norm * right_norm))


def tfidf_pair_scores(pairs: list[tuple[str, str]]) -> list[float]:
    if not pairs:
        return []
    corpus = [left for left, _right in pairs] + [right for _left, right in pairs]
    matrix = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).fit_transform(corpus)
    left_matrix = matrix[: len(pairs)]
    right_matrix = matrix[len(pairs) :]
    values = left_matrix.multiply(right_matrix).sum(axis=1)
    return [float(value) for value in np.asarray(values).ravel()]


def neural_pair_scores(
    pairs: list[tuple[str, str]],
    *,
    model_name: str = DEFAULT_MODEL,
) -> tuple[str, list[float], str | None]:
    """Return neural scores or TF-IDF fallback scores when model loading fails."""

    if not pairs:
        return "empty", [], "No pairs were provided."
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        return (
            "tfidf_fallback",
            tfidf_pair_scores(pairs),
            f"sentence-transformers unavailable: {exc}",
        )

    try:
        model = SentenceTransformer(model_name)
        texts = [left for left, _right in pairs] + [right for _left, right in pairs]
        embeddings = model.encode(texts, normalize_embeddings=True)
        left_embeddings = embeddings[: len(pairs)]
        right_embeddings = embeddings[len(pairs) :]
        scores = [
            float(cosine_similarity([left], [right])[0][0])
            for left, right in zip(left_embeddings, right_embeddings, strict=True)
        ]
        return "neural", scores, None
    except Exception as exc:
        return "tfidf_fallback", tfidf_pair_scores(pairs), f"neural model unavailable: {exc}"


def default_demo_pairs() -> list[tuple[str, str]]:
    return [
        ("Doom", "DOOM"),
        ("The Witcher 3: Wild Hunt", "Witcher 3"),
        ("Doom 3", "Doom 3: Resurrection of Evil"),
        ("Badass Hero", "Fury Unleashed"),
    ]


def write_report(
    pairs: list[tuple[str, str]],
    scores: list[float],
    *,
    mode: str,
    warning: str | None,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {"left_title": left, "right_title": right, "embedding_similarity": round(score, 6)}
        for (left, right), score in zip(pairs, scores, strict=True)
    ]
    csv_path = output_dir / "neural_embedding_pair_scores.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["left_title", "right_title", "embedding_similarity"],
        )
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "status": "ok" if mode == "neural" else "warning",
        "mode": mode,
        "warning": warning,
        "row_count": len(rows),
        "csv_path": str(csv_path),
        "model": DEFAULT_MODEL if mode == "neural" else None,
    }
    summary_path = output_dir / "neural_embedding_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run optional neural embedding research.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pairs = default_demo_pairs()
    mode, scores, warning = neural_pair_scores(pairs, model_name=args.model)
    summary = write_report(pairs, scores, mode=mode, warning=warning, output_dir=args.output_dir)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
