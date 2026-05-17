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
    *,
    source_game_rows: list[dict[str, Any]] | None = None,
    alias_rows: list[dict[str, Any]] | None = None,
    description_rows: list[dict[str, Any]] | None = None,
    rating_rows: list[dict[str, Any]] | None = None,
    popularity_rows: list[dict[str, Any]] | None = None,
    url_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    all_records = list(records.values())
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
            "release_date": sum(record.release_year is not None for record in source_records)
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

    total_records = len(all_records) or 1
    global_missing_rates = {
        "release_date": round(
            1
            - (
                sum(record.release_year is not None for record in all_records)
                / total_records
            ),
            6,
        ),
        "description": round(
            1 - (sum(record.has_description for record in all_records) / total_records),
            6,
        ),
        "developer": round(
            1 - (sum(bool(record.developers) for record in all_records) / total_records),
            6,
        ),
        "genre": round(
            1 - (sum(bool(record.genres) for record in all_records) / total_records),
            6,
        ),
        "platform": round(
            1 - (sum(bool(record.platforms) for record in all_records) / total_records),
            6,
        ),
    }

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
    wikidata_steam_ids = {
        record.external_ids["steam"]
        for (_, _), record in records.items()
        if record.source == "wikidata" and "steam" in record.external_ids
    }
    wikidata_igdb_ids = {
        record.external_ids["igdb"]
        for (_, _), record in records.items()
        if record.source == "wikidata" and "igdb" in record.external_ids
    }
    steam_records = {
        record.source_game_id for (_, _), record in records.items() if record.source == "steam"
    }
    igdb_records = {
        record.source_game_id: record
        for (_, _), record in records.items()
        if record.source == "igdb"
    }
    steam_source_game_rows = [
        row for row in (source_game_rows or []) if row.get("source") == "steam"
    ]
    steam_description_rows = [
        row for row in (description_rows or []) if row.get("source") == "steam"
    ]
    steam_rating_rows = [row for row in (rating_rows or []) if row.get("source") == "steam"]
    steam_popularity_rows = [row for row in (popularity_rows or []) if row.get("source") == "steam"]
    wikipedia_description_rows = [
        row for row in (description_rows or []) if row.get("source") == "wikipedia"
    ]
    igdb_alias_rows = [row for row in (alias_rows or []) if row.get("source") == "igdb"]
    wikipedia_url_rows = [row for row in (url_rows or []) if row.get("source") == "wikipedia"]
    wikipedia_page_ids = {str(row["source_game_id"]) for row in wikipedia_url_rows}
    wikipedia_summary_ids = {
        str(row["source_game_id"])
        for row in wikipedia_description_rows
        if row.get("description_type") == "summary" and row.get("description_text")
    }
    missing_wikipedia_extract_count = len(
        {
            str(row["source_game_id"])
            for row in wikipedia_description_rows
            if not str(row.get("description_text") or "").strip()
        }
    )
    short_wikipedia_extract_count = len(
        {
            str(row["source_game_id"])
            for row in wikipedia_description_rows
            if 0 < len(str(row.get("description_text") or "").strip()) < 80
        }
    )
    wikipedia_ru_page_ids = {
        str(row["source_game_id"])
        for row in wikipedia_url_rows
        if isinstance(row.get("source_specific_json"), dict)
        and row["source_specific_json"].get("language") == "ru"
    }
    wikipedia_en_page_ids = {
        str(row["source_game_id"])
        for row in wikipedia_url_rows
        if isinstance(row.get("source_specific_json"), dict)
        and row["source_specific_json"].get("language") == "en"
    }
    wikidata_ruwiki_sitelink_count = sum(
        "ruwiki" in record.url_types
        for (_, _), record in records.items()
        if record.source == "wikidata"
    )
    wikidata_enwiki_sitelink_count = sum(
        "enwiki" in record.url_types
        for (_, _), record in records.items()
        if record.source == "wikidata"
    )
    wikipedia_summary_coverage_rate = (
        round(
            len(wikipedia_summary_ids)
            / (wikidata_ruwiki_sitelink_count + wikidata_enwiki_sitelink_count),
            6,
        )
        if (wikidata_ruwiki_sitelink_count + wikidata_enwiki_sitelink_count)
        else 0.0
    )

    summary = {
        "record_count_by_source": record_count_by_source,
        "source_overlap_count": source_overlap_count,
        "missing_release_date_rate": global_missing_rates["release_date"],
        "missing_description_rate": global_missing_rates["description"],
        "missing_developer_rate": global_missing_rates["developer"],
        "missing_genre_rate": global_missing_rates["genre"],
        "missing_platform_rate": global_missing_rates["platform"],
        "duplicate_candidate_count": duplicate_candidate_count,
        "conflict_count_by_field": dict(Counter(row["conflict_type"] for row in conflict_report)),
        "language_coverage": dict(language_coverage),
        "external_id_coverage": dict(external_id_coverage),
        "candidate_pair_summary": dict(candidate_pair_summary),
        "steam_game_count": len(steam_records),
        "steam_appdetails_count": len(steam_records),
        "wikidata_steam_appid_count": len(wikidata_steam_ids),
        "steam_with_short_description_count": len(
            {
                str(row["source_game_id"])
                for row in steam_description_rows
                if row.get("description_type") == "short_description"
                and row.get("description_text")
            }
        ),
        "steam_with_supported_languages_count": len(
            {
                str(row["source_game_id"])
                for row in steam_source_game_rows
                if isinstance(row.get("quality_flags_json"), dict)
                and row["quality_flags_json"].get("has_supported_languages")
            }
        ),
        "steam_with_recommendations_count": len(
            {
                str(row["source_game_id"])
                for row in steam_popularity_rows
                if row.get("metric_name") == "recommendations_total"
                and row.get("metric_value") is not None
            }
        ),
        "steam_with_metacritic_count": len(
            {
                str(row["source_game_id"])
                for row in steam_rating_rows
                if row.get("rating_type") == "steam_metacritic"
                and row.get("rating_value") is not None
            }
        ),
        "steam_enrichment_coverage_rate": round(
            len(steam_records) / len(wikidata_steam_ids),
            6,
        )
        if wikidata_steam_ids
        else 0.0,
        "igdb_game_count": len(igdb_records),
        "wikidata_igdb_id_count": len(wikidata_igdb_ids),
        "igdb_with_themes_count": sum(bool(record.themes) for record in igdb_records.values()),
        "igdb_with_keywords_count": sum(bool(record.tags) for record in igdb_records.values()),
        "igdb_with_localizations_count": sum(
            row.get("alias_type") == "igdb_localization" for row in igdb_alias_rows
        ),
        "igdb_with_companies_count": sum(
            bool(record.developers or record.publishers) for record in igdb_records.values()
        ),
        "igdb_enrichment_coverage_rate": round(
            len(igdb_records) / len(wikidata_igdb_ids),
            6,
        )
        if wikidata_igdb_ids
        else 0.0,
        "wikipedia_page_count": len(wikipedia_page_ids),
        "wikipedia_ru_page_count": len(wikipedia_ru_page_ids),
        "wikipedia_en_page_count": len(wikipedia_en_page_ids),
        "wikipedia_summary_count": len(wikipedia_summary_ids),
        "wikidata_ruwiki_sitelink_count": wikidata_ruwiki_sitelink_count,
        "wikidata_enwiki_sitelink_count": wikidata_enwiki_sitelink_count,
        "wikipedia_summary_coverage_rate": wikipedia_summary_coverage_rate,
        "missing_wikipedia_extract_count": missing_wikipedia_extract_count,
        "short_wikipedia_extract_count": short_wikipedia_extract_count,
        "field_completeness_by_source": field_completeness_by_source,
        "missingness_report": missingness_report,
        "conflict_report": conflict_report,
    }
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate staging data-quality reports.")
    parser.add_argument(
        "--report-dir",
        default=str(project_root() / "data" / "artifacts" / "reports"),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview report paths without DB reads or file writes.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report_dir = Path(args.report_dir)
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
    summary = compute_data_quality_metrics(
        records,
        candidate_pairs,
        source_game_rows=repository.fetch_staging_rows("stg.source_games"),
        alias_rows=repository.fetch_staging_rows("stg.source_game_aliases"),
        description_rows=repository.fetch_staging_rows("stg.source_game_descriptions"),
        rating_rows=repository.fetch_staging_rows("stg.source_game_ratings"),
        popularity_rows=repository.fetch_staging_rows("stg.source_game_popularity"),
        url_rows=repository.fetch_staging_rows("stg.source_game_urls"),
    )

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
