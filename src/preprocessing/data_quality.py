"""Compute data quality and missingness reports for staging and ER prep."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from src.entity_resolution.corpus import SourceGameRecord, load_source_records
from src.ingestion.repository import IngestionRepository
from src.preprocessing.validate_staging_state import (
    validate_staging_state,
    validation_error_message,
)
from src.utils.config import project_root


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        rows = [{"status": "empty"}]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def compute_data_quality_metrics(
    records: dict[tuple[str, str], SourceGameRecord],
    candidate_pairs: list[dict[str, Any]],
) -> dict[str, Any]:
    by_source: dict[str, list[SourceGameRecord]] = defaultdict(list)
    for (source, _), record in records.items():
        by_source[source].append(record)

    record_count_by_source = {
        source: len(source_records) for source, source_records in by_source.items()
    }
    field_completeness_by_source: list[dict[str, Any]] = []
    missingness_report: list[dict[str, Any]] = []
    for source, source_records in sorted(by_source.items()):
        total = len(source_records) or 1
        metrics = {
            "release_date": sum(
                record.release_year is not None for record in source_records
            )
            / total,
            "description": sum(record.has_description for record in source_records) / total,
            "developer": sum(bool(record.developers) for record in source_records) / total,
            "genre": sum(bool(record.genres) for record in source_records) / total,
            "platform": sum(bool(record.platforms) for record in source_records) / total,
        }
        for field_name, completeness in metrics.items():
            field_completeness_by_source.append(
                {
                    "source": source,
                    "field_name": field_name,
                    "completeness_rate": round(completeness, 6),
                }
            )
            missingness_report.append(
                {
                    "source": source,
                    "field_name": field_name,
                    "missing_rate": round(1 - completeness, 6),
                }
            )

    source_overlap_count = sum(
        1
        for pair in candidate_pairs
        if pair.get("source_a") == "rawg" and pair.get("source_b") == "wikidata"
    )
    duplicate_candidate_count = max(
        0,
        len(candidate_pairs)
        - len(
            {
                (
                    str(pair["source_a"]),
                    str(pair["source_id_a"]),
                    str(pair["source_b"]),
                    str(pair["source_id_b"]),
                )
                for pair in candidate_pairs
            }
        ),
    )

    conflict_report: list[dict[str, Any]] = []
    language_coverage = Counter()
    external_id_coverage = Counter()
    for pair in candidate_pairs:
        key_a = (str(pair["source_a"]), str(pair["source_id_a"]))
        key_b = (str(pair["source_b"]), str(pair["source_id_b"]))
        if key_a not in records or key_b not in records:
            continue
        left = records[key_a]
        right = records[key_b]
        if (
            left.release_year is not None
            and right.release_year is not None
            and left.release_year != right.release_year
        ):
            conflict_report.append(
                {
                    "conflict_type": "release_year",
                    "source_id_a": left.source_game_id,
                    "source_id_b": right.source_game_id,
                    "left_value": left.release_year,
                    "right_value": right.release_year,
                }
            )
        if (
            left.name_normalized
            and right.name_normalized
            and left.name_normalized != right.name_normalized
        ):
            conflict_report.append(
                {
                    "conflict_type": "normalized_name",
                    "source_id_a": left.source_game_id,
                    "source_id_b": right.source_game_id,
                    "left_value": left.name_normalized,
                    "right_value": right.name_normalized,
                }
            )
        if left.developers and right.developers and not (left.developers & right.developers):
            conflict_report.append(
                {
                    "conflict_type": "developers",
                    "source_id_a": left.source_game_id,
                    "source_id_b": right.source_game_id,
                    "left_value": ",".join(sorted(left.developers)),
                    "right_value": ",".join(sorted(right.developers)),
                }
            )

    for (_, _), record in records.items():
        for language, aliases in record.alias_languages.items():
            language_coverage[language] += len(aliases)
        for external_source in record.external_ids:
            external_id_coverage[external_source] += 1

    candidate_pair_summary = Counter(
        str(pair.get("candidate_source") or "unknown") for pair in candidate_pairs
    )

    summary = {
        "record_count_by_source": record_count_by_source,
        "source_overlap_count": source_overlap_count,
        "missing_release_date_rate": round(
            sum(
                row["missing_rate"]
                for row in missingness_report
                if row["field_name"] == "release_date"
            ),
            6,
        ),
        "missing_description_rate": round(
            sum(
                row["missing_rate"]
                for row in missingness_report
                if row["field_name"] == "description"
            ),
            6,
        ),
        "missing_developer_rate": round(
            sum(
                row["missing_rate"]
                for row in missingness_report
                if row["field_name"] == "developer"
            ),
            6,
        ),
        "missing_genre_rate": round(
            sum(row["missing_rate"] for row in missingness_report if row["field_name"] == "genre"),
            6,
        ),
        "missing_platform_rate": round(
            sum(
                row["missing_rate"]
                for row in missingness_report
                if row["field_name"] == "platform"
            ),
            6,
        ),
        "duplicate_candidate_count": duplicate_candidate_count,
        "conflict_count_by_field": dict(Counter(row["conflict_type"] for row in conflict_report)),
        "language_coverage": dict(language_coverage),
        "external_id_coverage": dict(external_id_coverage),
        "candidate_pair_summary": dict(candidate_pair_summary),
        "field_completeness_by_source": field_completeness_by_source,
        "missingness_report": missingness_report,
        "conflict_report": conflict_report,
    }
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate staging data-quality reports.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview report paths without DB reads or file writes.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report_dir = project_root() / "data" / "artifacts" / "reports"
    if args.dry_run:
        print(
            {
                "report_dir": str(report_dir),
                "reports": [
                    "dq_summary.json",
                    "field_completeness_by_source.csv",
                    "source_record_counts.csv",
                    "source_overlap.csv",
                    "external_id_coverage.csv",
                    "candidate_pair_summary.csv",
                    "missingness_report.csv",
                    "conflict_report.csv",
                ],
            }
        )
        return 0

    repository = IngestionRepository()
    validation = validate_staging_state(repository)
    if not validation.ok:
        raise RuntimeError(validation_error_message(validation))
    records = load_source_records(repository)
    candidate_pairs = repository.fetch_candidate_pairs()
    summary = compute_data_quality_metrics(records, candidate_pairs)

    report_dir.mkdir(parents=True, exist_ok=True)
    with (report_dir / "dq_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                key: value
                for key, value in summary.items()
                if key
                not in {"field_completeness_by_source", "missingness_report", "conflict_report"}
            },
            handle,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
    write_csv(
        report_dir / "field_completeness_by_source.csv",
        summary["field_completeness_by_source"],
    )
    write_csv(
        report_dir / "source_record_counts.csv",
        [
            {"source": source, "record_count": count}
            for source, count in summary["record_count_by_source"].items()
        ],
    )
    write_csv(
        report_dir / "source_overlap.csv",
        [{"source_pair": "rawg_wikidata", "overlap_count": summary["source_overlap_count"]}],
    )
    write_csv(
        report_dir / "external_id_coverage.csv",
        [
            {"external_source": key, "count": value}
            for key, value in summary["external_id_coverage"].items()
        ],
    )
    write_csv(
        report_dir / "candidate_pair_summary.csv",
        [
            {"candidate_source": key, "count": value}
            for key, value in summary["candidate_pair_summary"].items()
        ],
    )
    write_csv(report_dir / "missingness_report.csv", summary["missingness_report"])
    write_csv(report_dir / "conflict_report.csv", summary["conflict_report"])
    print(
        {
            "record_count_by_source": summary["record_count_by_source"],
            "source_overlap_count": summary["source_overlap_count"],
            "duplicate_candidate_count": summary["duplicate_candidate_count"],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
