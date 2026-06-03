"""Generate a manifest for final ML-ready dataset artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from src.ingestion.repository import IngestionRepository
from src.preprocessing.export_ml_ready_datasets import DATASET_SPECS, build_output_paths
from src.preprocessing.validate_ml_ready_data import (
    validate_ml_ready_state,
    validation_error_message,
)
from src.utils.config import project_root


def _git_value(*args: str) -> str | None:
    try:
        output = subprocess.check_output(["git", *args], cwd=project_root(), text=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    value = output.strip()
    return value or None


def _parquet_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    return int(pl.read_parquet(path).height)


def build_manifest(
    repository: IngestionRepository,
    *,
    output_dir: Path,
    reports_dir: Path,
    manifest_path: Path,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    export_paths = build_output_paths(output_dir)
    row_counts = {name: _parquet_row_count(path) for name, path in export_paths.items()}
    row_counts_by_source = {
        source_name: (
            repository.count_rows("stg.source_game_descriptions", source=source_name)
            if source_name == "wikipedia"
            else repository.count_rows("stg.source_games", source=source_name)
        )
        for source_name in ("rawg", "wikidata", "steam", "wikipedia", "igdb")
    }
    candidate_pairs = repository.fetch_candidate_pairs()
    weak_label_count = sum(str(pair.get("label_value") or "") == "1" for pair in candidate_pairs)

    return {
        "created_at": datetime.now(UTC).isoformat(),
        "git_branch": _git_value("branch", "--show-current"),
        "git_commit": _git_value("rev-parse", "HEAD"),
        "sources_included": {
            "required": ["rawg", "wikidata"],
            "optional": ["steam", "wikipedia", "igdb"],
        },
        "record_counts_per_dataset": row_counts,
        "row_counts_per_source": row_counts_by_source,
        "candidate_pair_count": len(candidate_pairs),
        "weak_label_count": weak_label_count,
        "dq_report_paths": {
            "dq_summary": str(reports_dir / "dq_summary.json"),
            "data_stage_summary": str(reports_dir / "data_stage_summary.md"),
            "source_coverage": str(reports_dir / "source_coverage.csv"),
            "feature_base_summary": str(reports_dir / "feature_base_summary.csv"),
            "manual_review_seed_summary": str(reports_dir / "manual_review_seed_summary.csv"),
            "anomaly_report": str(reports_dir / "anomaly_report.csv"),
        },
        "export_paths": {name: str(path) for name, path in export_paths.items()},
        "schema_versions": {
            "staging": "v1",
            "entity_resolution": "v1",
            "manifest": "v1",
        },
        "warnings": warnings or [],
        "manifest_path": str(manifest_path),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate ML-ready dataset manifest.")
    parser.add_argument("--output-dir", default=str(project_root() / "data" / "processed"))
    parser.add_argument(
        "--reports-dir",
        default=str(project_root() / "data" / "artifacts" / "reports"),
    )
    parser.add_argument(
        "--manifest-path",
        default=str(
            project_root() / "data" / "artifacts" / "manifests" / "ml_ready_dataset_manifest.json"
        ),
    )
    parser.add_argument("--allow-empty", action="store_true", help="Allow empty data state.")
    parser.add_argument("--dry-run", action="store_true", help="Preview manifest location only.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run:
        print(
            {
                "manifest_path": args.manifest_path,
                "output_dir": args.output_dir,
                "reports_dir": args.reports_dir,
                "datasets": sorted(DATASET_SPECS),
            }
        )
        return 0

    repository = IngestionRepository()
    validation = validate_ml_ready_state(
        repository,
        allow_empty=args.allow_empty,
        output_dir=args.output_dir,
        reports_dir=args.reports_dir,
        manifests_dir=str(Path(args.manifest_path).parent),
    )
    if not validation.ok:
        raise RuntimeError(validation_error_message(validation))

    manifest_path = Path(args.manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(
        repository,
        output_dir=Path(args.output_dir),
        reports_dir=Path(args.reports_dir),
        manifest_path=manifest_path,
        warnings=validation.warnings,
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print({"manifest_path": str(manifest_path), "dataset_count": len(DATASET_SPECS)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
