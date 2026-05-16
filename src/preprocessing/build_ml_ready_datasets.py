"""Orchestrate the final local ML-ready dataset build without external APIs."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from src.entity_resolution.build_candidate_pairs import (
    generate_candidate_pairs,
    summarize_candidate_pairs,
)
from src.entity_resolution.build_feature_base import (
    build_feature_row,
    summarize_feature_rows,
)
from src.entity_resolution.build_manual_review_seed import (
    build_manual_review_rows,
    summarize_manual_review_rows,
)
from src.entity_resolution.corpus import load_source_records
from src.ingestion.repository import IngestionRepository
from src.preprocessing.anomaly_reports import main as anomaly_main
from src.preprocessing.build_dataset_manifest import main as manifest_main
from src.preprocessing.data_quality import write_csv
from src.preprocessing.export_analysis_data import main as export_analysis_main
from src.preprocessing.export_ml_ready_datasets import main as export_ml_ready_main
from src.preprocessing.source_coverage import main as source_coverage_main
from src.preprocessing.validate_ml_ready_data import (
    validate_ml_ready_state,
    validation_error_message,
)
from src.utils.config import project_root


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build final ML-ready local datasets.")
    parser.add_argument("--dry-run", action="store_true", help="Preview build steps only.")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild candidate/features first.")
    parser.add_argument("--limit", type=int, help="Optional limit for debug-sized local runs.")
    parser.add_argument("--output-dir", default=str(project_root() / "data" / "processed"))
    parser.add_argument(
        "--reports-dir",
        default=str(project_root() / "data" / "artifacts" / "reports"),
    )
    parser.add_argument("--allow-empty", action="store_true", help="Allow empty data state.")
    return parser


def _summary_markdown(
    *,
    candidate_summary: dict[str, Any],
    feature_summary: dict[str, Any],
    review_summary: list[dict[str, Any]],
) -> str:
    lines = [
        "# Data Stage Summary",
        "",
        "## Candidate pairs",
        f"- candidate_pair_count: {candidate_summary['candidate_pair_count']}",
        f"- positive_weak_label_count: {candidate_summary['positive_weak_label_count']}",
        f"- manual_review_candidate_count: {candidate_summary['manual_review_candidate_count']}",
        "",
        "## Feature base",
        f"- feature_pair_count: {feature_summary['feature_pair_count']}",
        f"- description_available_count: {feature_summary['description_available_count']}",
        (
            "- description_language_match_count: "
            f"{feature_summary['description_language_match_count']}"
        ),
        "",
        "## Manual review seed",
    ]
    for row in review_summary:
        lines.append(f"- {row['review_category']}: {row['pair_count']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    reports_dir = Path(args.reports_dir)
    output_dir = Path(args.output_dir)
    manifests_dir = project_root() / "data" / "artifacts" / "manifests"
    if args.dry_run:
        print(
            {
                "allow_empty": args.allow_empty,
                "rebuild": args.rebuild,
                "limit": args.limit,
                "output_dir": str(output_dir),
                "reports_dir": str(reports_dir),
                "steps": [
                    "validate required input state",
                    "refresh candidate pairs",
                    "refresh feature base",
                    "run source coverage",
                    "run data quality",
                    "run anomaly reports",
                    "export analysis data",
                    "build manual review seed",
                    "export ML-ready datasets",
                    "generate manifest",
                ],
            }
        )
        return 0

    repository = IngestionRepository()
    validation = validate_ml_ready_state(
        repository,
        allow_empty=args.allow_empty,
        allow_missing_artifacts=True,
        output_dir=str(output_dir),
        reports_dir=str(reports_dir),
        manifests_dir=str(manifests_dir),
    )
    if not validation.ok:
        raise RuntimeError(validation_error_message(validation))

    records = load_source_records(repository)
    if args.rebuild:
        repository.delete_entity_resolution_features()
        repository.delete_candidate_pairs()

    candidate_pairs = generate_candidate_pairs(records, limit=args.limit)
    for pair in candidate_pairs:
        repository.upsert_candidate_pair(**pair)
    candidate_pairs = repository.fetch_candidate_pairs(limit=args.limit)
    candidate_summary = summarize_candidate_pairs(candidate_pairs)

    feature_rows: list[dict[str, object]] = []
    for pair in candidate_pairs:
        key_a = (str(pair["source_a"]), str(pair["source_id_a"]))
        key_b = (str(pair["source_b"]), str(pair["source_id_b"]))
        if key_a not in records or key_b not in records:
            continue
        row = build_feature_row(pair, records[key_a], records[key_b])
        feature_rows.append(row)
        repository.upsert_entity_resolution_features(**row)
    feature_summary = summarize_feature_rows(feature_rows)

    source_coverage_main(["--report-dir", str(reports_dir)])
    from src.preprocessing.data_quality import main as data_quality_main

    data_quality_main(["--report-dir", str(reports_dir)])
    anomaly_main(["--report-dir", str(reports_dir)])
    export_analysis_main(["--output-dir", str(output_dir)])

    manual_review_rows = build_manual_review_rows(
        records,
        candidate_pairs,
        {str(row["pair_id"]): row for row in feature_rows},
    )
    review_summary = summarize_manual_review_rows(manual_review_rows)
    write_csv(reports_dir / "manual_review_seed_summary.csv", review_summary)
    write_csv(
        reports_dir / "feature_base_summary.csv",
        [
            {"metric": key, "value": value}
            for key, value in feature_summary.items()
            if key != "missing_feature_reason_count"
        ]
        + [
            {"metric": f"missing_reason:{key}", "value": value}
            for key, value in feature_summary["missing_feature_reason_count"].items()
        ],
    )
    (reports_dir / "data_stage_summary.md").write_text(
        _summary_markdown(
            candidate_summary=candidate_summary,
            feature_summary=feature_summary,
            review_summary=review_summary,
        ),
        encoding="utf-8",
    )

    export_ml_ready_main(
        ["--output-dir", str(output_dir)] + (["--allow-empty"] if args.allow_empty else [])
    )
    manifest_main(
        [
            "--output-dir",
            str(output_dir),
            "--reports-dir",
            str(reports_dir),
            "--manifest-path",
            str(manifests_dir / "ml_ready_dataset_manifest.json"),
        ]
        + (["--allow-empty"] if args.allow_empty else [])
    )

    print(
        {
            "candidate_summary": candidate_summary,
            "feature_summary": feature_summary,
            "manual_review_seed_count": len(manual_review_rows),
            "reports_dir": str(reports_dir),
            "output_dir": str(output_dir),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
