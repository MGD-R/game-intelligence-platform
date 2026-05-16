"""Generate source coverage and deterministic matching reports."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from src.entity_resolution.corpus import load_source_records
from src.ingestion.repository import IngestionRepository
from src.preprocessing.validate_data_stage_inputs import ensure_stage_inputs
from src.utils.config import project_root


def compute_coverage_metrics(
    records, candidate_pairs: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rawg_records = [record for key, record in records.items() if key[0] == "rawg"]
    wikidata_records = [record for key, record in records.items() if key[0] == "wikidata"]
    wikidata_rawg_ids = {
        record.external_ids["rawg"]
        for record in wikidata_records
        if "rawg" in record.external_ids
    }
    deterministic_matches = [
        pair for pair in candidate_pairs if pair.get("label_source") == "wikidata_rawg_external_id"
    ]
    candidate_summary = {
        "external_id_positive": 0,
        "same_normalized_name": 0,
        "same_release_year_and_similar_name": 0,
        "shared_alias": 0,
    }
    for pair in candidate_pairs:
        source_name = str(pair.get("candidate_source") or "")
        if source_name in candidate_summary:
            candidate_summary[source_name] += 1

    rawg_game_count = len(rawg_records)
    wikidata_game_count = len(wikidata_records)
    matched_rawg_ids = {str(pair["source_id_a"]) for pair in deterministic_matches}
    matched_wikidata_ids = {str(pair["source_id_b"]) for pair in deterministic_matches}
    rawg_wikidata_match_rate = round(
        len(matched_rawg_ids) / rawg_game_count,
        6,
    ) if rawg_game_count else 0.0
    metrics = {
        "rawg_game_count": rawg_game_count,
        "wikidata_game_count": wikidata_game_count,
        "wikidata_rawg_external_id_count": len(wikidata_rawg_ids),
        "rawg_wikidata_matched_count": len(deterministic_matches),
        "rawg_wikidata_match_rate": rawg_wikidata_match_rate,
        "positive_weak_label_count": len(deterministic_matches),
        "unmatched_rawg_count": rawg_game_count - len(matched_rawg_ids),
        "unmatched_wikidata_count": wikidata_game_count - len(matched_wikidata_ids),
        "steam_appid_count_from_wikidata": sum(
            "steam" in record.external_ids for record in wikidata_records
        ),
        "igdb_id_count_from_wikidata": sum(
            "igdb" in record.external_ids for record in wikidata_records
        ),
        "ruwiki_sitelink_count": sum("ruwiki" in record.url_types for record in wikidata_records),
        "enwiki_sitelink_count": sum("enwiki" in record.url_types for record in wikidata_records),
    }
    source_rows = [
        {"source": "rawg", "game_count": rawg_game_count},
        {"source": "wikidata", "game_count": wikidata_game_count},
    ]
    external_id_rows = [
        {"source": "wikidata", "external_source": "rawg", "count": len(wikidata_rawg_ids)},
        {
            "source": "wikidata",
            "external_source": "steam",
            "count": sum("steam" in record.external_ids for record in wikidata_records),
        },
        {
            "source": "wikidata",
            "external_source": "igdb",
            "count": sum("igdb" in record.external_ids for record in wikidata_records),
        },
    ]
    return metrics, source_rows, external_id_rows, candidate_summary


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        rows = [{"status": "empty"}]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate source coverage reports.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview report generation without DB reads or file writes.",
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
                    "source_coverage.csv",
                    "external_id_coverage.csv",
                    "candidate_pair_summary.csv",
                    "deterministic_match_summary.json",
                ],
            }
        )
        return 0

    repository = IngestionRepository()
    ensure_stage_inputs(repository)
    records = load_source_records(repository)
    candidate_pairs = repository.fetch_candidate_pairs()
    metrics, source_rows, external_id_rows, candidate_summary = compute_coverage_metrics(
        records,
        candidate_pairs,
    )
    write_csv(report_dir / "source_coverage.csv", source_rows)
    write_csv(report_dir / "external_id_coverage.csv", external_id_rows)
    write_csv(
        report_dir / "candidate_pair_summary.csv",
        [{"candidate_source": key, "count": value} for key, value in candidate_summary.items()],
    )
    with (report_dir / "deterministic_match_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=True, indent=2, sort_keys=True)
    print(metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
