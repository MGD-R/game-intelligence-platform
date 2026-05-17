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
    "raw.rawg_reference_data": "rawg_reference_data.jsonl.gz",
    "raw.wikidata_sparql_results": "wikidata_sparql_results.jsonl.gz",
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


def write_checksums(root: Path, paths: list[Path]) -> Path:
    checksum_path = root / "checksums.sha256"
    lines = [
        f"{checksum_for_file(path)}  {path.relative_to(root).as_posix()}" for path in sorted(paths)
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
) -> dict[str, Any]:
    row_counts = {
        "raw.rawg_game_index": repository.count_rows("raw.rawg_game_index"),
        "stg.source_games": repository.count_rows("stg.source_games"),
        "ml.entity_candidate_pairs": repository.count_rows("ml.entity_candidate_pairs"),
    }
    api_calls_by_source = {
        source_name: 0 for source_name in ("rawg", "wikidata", "steam", "wikipedia", "igdb")
    }
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
        "pack_root": str(pack_root),
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path
