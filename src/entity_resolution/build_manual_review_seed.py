"""Build a compact manual-review seed dataset from candidate pairs and features."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from src.entity_resolution.corpus import load_source_records
from src.ingestion.repository import IngestionRepository
from src.preprocessing.export_ml_ready_base import write_parquet
from src.preprocessing.validate_ml_ready_data import (
    validate_ml_ready_state,
    validation_error_message,
)
from src.utils.config import project_root


def build_manual_review_rows(
    records: dict[tuple[str, str], Any],
    candidate_pairs: list[dict[str, Any]],
    feature_rows: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_categories: set[tuple[str, str]] = set()
    for pair in candidate_pairs:
        key_a = (str(pair["source_a"]), str(pair["source_id_a"]))
        key_b = (str(pair["source_b"]), str(pair["source_id_b"]))
        if key_a not in records or key_b not in records:
            continue
        source_a = records[key_a]
        source_b = records[key_b]
        pair_id = str(pair["pair_id"])
        feature_row = feature_rows.get(pair_id, {})
        categories: list[str] = []
        if str(pair.get("label_value") or "") == "1":
            categories.append("deterministic_positive")
        if pair.get("candidate_source") == "same_normalized_name" and (
            feature_row.get("release_year_diff") not in {None, 0}
        ):
            categories.append("same_title_different_year")
        if pair.get("candidate_source") == "same_release_year_and_similar_name":
            categories.append("similar_title")
        if pair.get("candidate_source") == "shared_alias":
            categories.append("alias_overlap")
        if feature_row.get("developer_overlap") == 0 or feature_row.get("publisher_overlap") == 0:
            categories.append("potential_conflict")

        if not categories:
            continue

        for category in categories:
            category_key = (category, pair_id)
            if category_key in seen_categories:
                continue
            seen_categories.add(category_key)
            rows.append(
                {
                    "pair_id": pair_id,
                    "review_category": category,
                    "source_a": source_a.source,
                    "source_id_a": source_a.source_game_id,
                    "name_a": source_a.name,
                    "release_year_a": source_a.release_year,
                    "source_b": source_b.source,
                    "source_id_b": source_b.source_game_id,
                    "name_b": source_b.name,
                    "release_year_b": source_b.release_year,
                    "candidate_source": pair.get("candidate_source"),
                    "label_source": pair.get("label_source"),
                    "label_value": pair.get("label_value"),
                    "confidence": pair.get("confidence"),
                    "name_similarity": feature_row.get("name_similarity"),
                    "alias_similarity": feature_row.get("alias_similarity"),
                    "release_year_diff": feature_row.get("release_year_diff"),
                    "external_id_exact_match": feature_row.get("external_id_exact_match"),
                    "description_available_flag": feature_row.get("description_available_flag"),
                    "description_language_match": feature_row.get("description_language_match"),
                    "source_count_signal": feature_row.get("source_count_signal"),
                    "features_json": feature_row.get("features_json", {}),
                }
            )
    return rows


def summarize_manual_review_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(str(row["review_category"]) for row in rows)
    return [
        {"review_category": category, "pair_count": count}
        for category, count in sorted(counts.items())
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build manual-review seed parquet.")
    parser.add_argument(
        "--output-path",
        default=str(project_root() / "data" / "processed" / "manual_review_seed.parquet"),
    )
    parser.add_argument("--allow-empty", action="store_true", help="Allow empty output.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files.")
    parser.add_argument("--limit", type=int, help="Optional candidate-pair limit.")
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

    repository = IngestionRepository()
    validation = validate_ml_ready_state(repository, allow_empty=args.allow_empty)
    if not validation.ok:
        raise RuntimeError(validation_error_message(validation))

    records = load_source_records(repository)
    candidate_pairs = repository.fetch_candidate_pairs(limit=args.limit)
    feature_rows = {
        str(row["pair_id"]): row
        for row in repository.fetch_entity_resolution_features(limit=args.limit)
    }
    rows = build_manual_review_rows(records, candidate_pairs, feature_rows)
    if not rows and not args.allow_empty:
        raise RuntimeError(
            "Manual review seed is empty. Build candidate pairs and feature base first."
        )

    output_path = Path(args.output_path)
    write_parquet(output_path, rows)
    summary = summarize_manual_review_rows(rows)
    print(
        {
            "output_path": str(output_path),
            "manual_review_seed_count": len(rows),
            "category_summary": summary,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
