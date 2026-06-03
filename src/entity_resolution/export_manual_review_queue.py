"""Export DB-backed ER manual review queues to CSV and JSON summaries."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from src.ingestion.repository import IngestionRepository
from src.utils.config import project_root

DEFAULT_COLUMNS = [
    "review_id",
    "pair_id",
    "source_a",
    "source_id_a",
    "name_a",
    "release_year_a",
    "rawg_url",
    "source_b",
    "source_id_b",
    "name_b",
    "release_year_b",
    "igdb_url",
    "candidate_source",
    "label_source",
    "label_value",
    "name_similarity",
    "alias_similarity",
    "release_year_diff",
    "same_game_probability",
    "model_decision",
    "selection_strategy",
    "priority_score",
    "review_status",
    "review_label",
    "reviewer",
    "review_notes",
    "invalid_display_name_flag",
]


def normalize_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: normalize_value(value) for key, value in row.items()} for row in rows]


def build_review_query(*, status: str, limit: int | None) -> tuple[str, tuple[object, ...]]:
    clauses: list[str] = []
    params: list[object] = []
    if status != "all":
        clauses.append("r.review_status = %s")
        params.append(status)
    where_sql = "WHERE " + " AND ".join(clauses) if clauses else ""
    limit_sql = ""
    if limit is not None:
        limit_sql = "LIMIT %s"
        params.append(limit)

    query = f"""
        SELECT
            r.review_id::TEXT AS review_id,
            v.pair_id::TEXT AS pair_id,
            v.source_a,
            v.source_id_a,
            v.name_a,
            v.release_year_a,
            v.rawg_url,
            v.source_b,
            v.source_id_b,
            v.name_b,
            v.release_year_b,
            v.igdb_url,
            v.candidate_source,
            v.label_source,
            v.label_value,
            v.name_similarity,
            v.alias_similarity,
            v.release_year_diff,
            v.same_game_probability,
            v.model_decision,
            r.selection_strategy,
            r.priority_score,
            r.review_status,
            r.review_label,
            r.reviewer,
            r.review_notes,
            (
                v.name_a IS NULL
                OR v.name_b IS NULL
                OR v.name_a ~ '^Q[0-9]+$'
                OR v.name_b ~ '^Q[0-9]+$'
                OR v.name_a ~ '^[0-9]+$'
                OR v.name_b ~ '^[0-9]+$'
                OR length(btrim(v.name_a)) <= 2
                OR length(btrim(v.name_b)) <= 2
            ) AS invalid_display_name_flag
        FROM ml.entity_resolution_manual_reviews r
        JOIN ml.v_entity_resolution_review_candidates v
            ON v.pair_id = r.pair_id
        {where_sql}
        ORDER BY
            r.selection_strategy,
            r.priority_score DESC,
            v.name_similarity ASC NULLS LAST,
            v.pair_id
        {limit_sql}
    """
    return query, tuple(params)


def fetch_review_rows(
    repository: IngestionRepository,
    *,
    status: str,
    limit: int | None,
) -> list[dict[str, Any]]:
    query, params = build_review_query(status=status, limit=limit)
    with repository.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return normalize_rows(list(cursor.fetchall()))


def summarize_review_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "row_count": len(rows),
        "by_selection_strategy": {},
        "by_candidate_source": {},
        "by_model_decision": {},
        "invalid_display_name_count": 0,
    }
    for row in rows:
        for key, output_key in (
            ("selection_strategy", "by_selection_strategy"),
            ("candidate_source", "by_candidate_source"),
            ("model_decision", "by_model_decision"),
        ):
            value = str(row.get(key) or "unknown")
            bucket = summary[output_key]
            bucket[value] = int(bucket.get(value, 0)) + 1
        if bool(row.get("invalid_display_name_flag")):
            summary["invalid_display_name_count"] += 1
    return summary


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=DEFAULT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def export_manual_review_queue(
    *,
    repository: IngestionRepository,
    output_dir: Path,
    status: str,
    limit: int | None,
) -> dict[str, Any]:
    rows = fetch_review_rows(repository, status=status, limit=limit)
    suffix = status if status != "all" else "all"
    csv_path = output_dir / f"entity_resolution_manual_review_{suffix}.csv"
    summary_path = output_dir / f"entity_resolution_manual_review_{suffix}_summary.json"
    summary = summarize_review_rows(rows)
    write_csv(csv_path, rows)
    write_json(summary_path, summary)
    return {
        "status": status,
        "row_count": len(rows),
        "csv_path": str(csv_path),
        "summary_path": str(summary_path),
        "summary": summary,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export DB-backed ER manual review queues.")
    parser.add_argument(
        "--status",
        choices=["pending", "reviewed", "unsure", "skipped", "all"],
        default="pending",
        help="Review status to export.",
    )
    parser.add_argument("--limit", type=int, help="Optional max row count.")
    parser.add_argument(
        "--output-dir",
        default=str(project_root() / "data" / "artifacts" / "reports" / "entity_resolution"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        export_manual_review_queue(
            repository=IngestionRepository(),
            output_dir=Path(args.output_dir),
            status=args.status,
            limit=args.limit,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
