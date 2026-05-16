"""Rule-based anomaly and duplicate reports for staging analysis."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from src.entity_resolution.corpus import SourceGameRecord, load_source_records
from src.ingestion.repository import IngestionRepository
from src.preprocessing.validate_staging_state import (
    validate_staging_state,
    validation_error_message,
)
from src.utils.config import project_root

TITLE_RISK_TOKENS = ("edition", "dlc", "bundle", "collection", "demo", "trial", "remaster")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        rows = [{"status": "empty"}]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_anomaly_rows(
    records: dict[tuple[str, str], SourceGameRecord],
    ratings_rows: list[dict[str, Any]],
    description_rows: list[dict[str, Any]],
    candidate_pairs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    by_name: dict[tuple[str, str], list[SourceGameRecord]] = {}
    for (_, _), record in records.items():
        if not record.name_normalized:
            anomalies.append(
                {
                    "anomaly_type": "missing_required_fields",
                    "source": record.source,
                    "source_game_id": record.source_game_id,
                    "detail": "missing normalized title",
                }
            )
        if record.release_year is not None and (
            record.release_year < 1970 or record.release_year > 2030
        ):
            anomalies.append(
                {
                    "anomaly_type": "suspicious_release_year",
                    "source": record.source,
                    "source_game_id": record.source_game_id,
                    "detail": str(record.release_year),
                }
            )
        if any(token in record.name.lower() for token in TITLE_RISK_TOKENS):
            anomalies.append(
                {
                    "anomaly_type": "possible_dlc_or_edition_by_title",
                    "source": record.source,
                    "source_game_id": record.source_game_id,
                    "detail": record.name,
                }
            )
        if record.name_normalized:
            by_name.setdefault((record.source, record.name_normalized), []).append(record)

    for (source, normalized_name), rows in by_name.items():
        if len(rows) > 1:
            anomalies.append(
                {
                    "anomaly_type": "duplicate_normalized_names",
                    "source": source,
                    "source_game_id": ",".join(sorted(row.source_game_id for row in rows)),
                    "detail": normalized_name,
                }
            )

    for row in ratings_rows:
        if row.get("rating_value") is None:
            continue
        rating_value = float(row["rating_value"])
        rating_count = int(row["rating_count"]) if row.get("rating_count") is not None else 0
        if rating_value >= 4.5 and rating_count <= 3:
            anomalies.append(
                {
                    "anomaly_type": "high_rating_low_votes",
                    "source": str(row["source"]),
                    "source_game_id": str(row["source_game_id"]),
                    "detail": f"value={rating_value}, count={rating_count}",
                }
            )

    for row in description_rows:
        text = str(row.get("description_text") or "").strip()
        if not text:
            anomalies.append(
                {
                    "anomaly_type": "empty_descriptions",
                    "source": str(row["source"]),
                    "source_game_id": str(row["source_game_id"]),
                    "detail": "empty",
                }
            )
        elif len(text) < 40:
            anomalies.append(
                {
                    "anomaly_type": "very_short_descriptions",
                    "source": str(row["source"]),
                    "source_game_id": str(row["source_game_id"]),
                    "detail": text,
                }
            )

    deterministic_pairs = [
        pair for pair in candidate_pairs if pair.get("label_source") == "wikidata_rawg_external_id"
    ]
    if len(deterministic_pairs) > 1:
        anomalies.append(
            {
                "anomaly_type": "canonical_risk_clusters",
                "source": "rawg_wikidata",
                "source_game_id": str(len(deterministic_pairs)),
                "detail": "multiple deterministic pairs require canonical review",
            }
        )
    return anomalies


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate rule-based anomaly reports.")
    parser.add_argument(
        "--report-dir",
        default=str(project_root() / "data" / "artifacts" / "reports"),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview anomaly report path without DB reads.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report_path = Path(args.report_dir) / "anomaly_report.csv"
    if args.dry_run:
        print({"report": str(report_path)})
        return 0

    repository = IngestionRepository()
    validation = validate_staging_state(repository)
    if not validation.ok:
        raise RuntimeError(validation_error_message(validation))
    records = load_source_records(repository)
    anomalies = build_anomaly_rows(
        records,
        repository.fetch_staging_rows("stg.source_game_ratings"),
        repository.fetch_staging_rows("stg.source_game_descriptions"),
        repository.fetch_candidate_pairs(),
    )
    write_csv(report_path, anomalies)
    print({"anomaly_count": len(anomalies), "report": str(report_path)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
