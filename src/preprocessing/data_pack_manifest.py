"""Manifest helpers for file-based data pack export/import."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.ingestion.repository import IngestionRepository
from src.utils.config import project_root

RAW_TABLE_EXPORTS = {
    "raw.rawg_game_index": "rawg_game_index.jsonl.gz",
    "raw.rawg_game_details": "rawg_game_details.jsonl.gz",
    "raw.rawg_reference_data": "rawg_reference_data.jsonl.gz",
    "raw.wikidata_sparql_results": "wikidata_sparql_results.jsonl.gz",
    "raw.wikidata_entities": "wikidata_entities.jsonl.gz",
    "raw.steam_app_details": "steam_app_details.jsonl.gz",
    "raw.wikipedia_pages": "wikipedia_pages.jsonl.gz",
    "raw.igdb_games": "igdb_games.jsonl.gz",
    "raw.igdb_reference_data": "igdb_reference_data.jsonl.gz",
}

PROCESSED_EXPORTS = (
    "source_games.parquet",
    "source_aliases.parquet",
    "source_external_ids.parquet",
    "entity_candidate_pairs.parquet",
    "entity_resolution_feature_base.parquet",
)

REPORT_EXPORTS = (
    "dq_summary.json",
    "source_coverage.csv",
    "data_stage_summary.md",
)


def _path_exists(root: Path, *parts: str) -> bool:
    return (root.joinpath(*parts)).exists()


def git_value(*args: str) -> str | None:
    try:
        output = subprocess.check_output(["git", *args], cwd=project_root(), text=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return output.strip() or None


def checksum_for_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_checksums_map(root: Path, paths: list[Path]) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): checksum_for_file(path)
        for path in sorted(paths)
        if path.exists()
    }


def write_checksums(root: Path, paths: list[Path]) -> Path:
    checksum_path = root / "checksums.sha256"
    lines = [
        f"{digest}  {relative}" for relative, digest in build_checksums_map(root, paths).items()
    ]
    checksum_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return checksum_path


def build_data_pack_manifest(
    repository: IngestionRepository,
    *,
    data_pack_id: str,
    pack_root: Path,
    sources: list[str],
    warnings: list[str] | None = None,
    checksums: dict[str, str] | None = None,
) -> dict[str, Any]:
    row_counts = {table_name: repository.count_rows(table_name) for table_name in RAW_TABLE_EXPORTS}
    row_counts.update(
        {
            "stg.source_games": repository.count_rows("stg.source_games"),
            "stg.source_game_external_ids": repository.count_rows("stg.source_game_external_ids"),
            "ml.entity_candidate_pairs": repository.count_rows("ml.entity_candidate_pairs"),
            "ml.entity_resolution_features": repository.count_rows("ml.entity_resolution_features"),
        }
    )
    api_calls_by_source = {
        source_name: repository.count_api_requests(source_name)
        for source_name in ("rawg", "wikidata", "steam", "wikipedia", "igdb")
    }
    rawg_game_count = repository.count_rows("stg.source_games", source="rawg")
    wikidata_game_count = repository.count_rows("stg.source_games", source="wikidata")
    wikidata_rawg_external_id_count = len(
        [
            row
            for row in repository.fetch_staging_rows(
                "stg.source_game_external_ids",
                source="wikidata",
            )
            if str(row.get("external_source") or "") == "rawg"
        ]
    )
    processed_exports_ready = all(
        _path_exists(pack_root, "processed", name) for name in PROCESSED_EXPORTS
    )
    report_exports_ready = all(
        _path_exists(pack_root, "reports", name) for name in REPORT_EXPORTS
    )
    step_status = {
        "rawg_raw": (
            row_counts["raw.rawg_game_index"] > 0
            and row_counts["raw.rawg_reference_data"] > 0
        ),
        "wikidata_raw": row_counts["raw.wikidata_sparql_results"] > 0,
        "rawg_staging": rawg_game_count > 0,
        "wikidata_staging": wikidata_game_count > 0,
        "external_id_matching": wikidata_rawg_external_id_count > 0,
        "candidate_pairs": row_counts["ml.entity_candidate_pairs"] > 0,
        "feature_base": row_counts["ml.entity_resolution_features"] > 0,
        "dq_reports": report_exports_ready,
        "ml_ready_exports": processed_exports_ready,
    }
    completed_steps = [name for name, ok in step_status.items() if ok]
    failed_steps = [name for name, ok in step_status.items() if not ok]
    if not completed_steps:
        run_status = "failed"
    elif failed_steps:
        run_status = "partial"
    else:
        run_status = "completed"
    return {
        "data_pack_id": data_pack_id,
        "created_at": datetime.now(UTC).isoformat(),
        "git_branch": git_value("branch", "--show-current"),
        "git_commit": git_value("rev-parse", "HEAD"),
        "sources": sources,
        "api_calls_by_source": api_calls_by_source,
        "row_counts": row_counts,
        "cache_root": "raw/cache",
        "processed_root": "processed",
        "reports_root": "reports",
        "warnings": warnings or [],
        "checksums": checksums or {},
        "pack_root": str(pack_root),
        "run_status": run_status,
        "ml_ready": (
            step_status["candidate_pairs"]
            and step_status["feature_base"]
            and step_status["ml_ready_exports"]
        ),
        "completed_steps": completed_steps,
        "failed_steps": failed_steps,
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path
