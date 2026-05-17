"""Export file-based data packs for restore without API calls."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
from pathlib import Path

from src.ingestion.repository import IngestionRepository
from src.ingestion.request_cache import ResponseCache
from src.preprocessing.data_pack_manifest import (
    PROCESSED_EXPORTS,
    RAW_TABLE_EXPORTS,
    REPORT_EXPORTS,
    build_checksums_map,
    build_data_pack_manifest,
    write_checksums,
    write_manifest,
)
from src.utils.config import project_root


def _normalize_row(row: dict[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for key, value in row.items():
        if hasattr(value, "isoformat"):
            normalized[key] = value.isoformat()  # type: ignore[call-arg]
        else:
            normalized[key] = value
    return normalized


def export_jsonl_gz(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(_normalize_row(row), ensure_ascii=True, sort_keys=True) + "\n")


def copy_if_exists(source: Path, destination: Path) -> bool:
    if not source.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export a local data pack.")
    parser.add_argument("--output", default=str(project_root() / "data_packs" / "gip_demo_local"))
    parser.add_argument("--include-cache", action="store_true")
    parser.add_argument("--include-processed", action="store_true")
    parser.add_argument("--include-reports", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_root = Path(args.output)
    if args.dry_run:
        print(
            {
                "output": str(output_root),
                "raw_exports": RAW_TABLE_EXPORTS,
                "processed_exports": list(PROCESSED_EXPORTS),
                "report_exports": list(REPORT_EXPORTS),
                "include_cache": args.include_cache,
                "include_processed": args.include_processed,
                "include_reports": args.include_reports,
            }
        )
        return 0

    repository = IngestionRepository()
    output_root.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []

    raw_jsonl_root = output_root / "raw" / "jsonl"
    for table_name, filename in RAW_TABLE_EXPORTS.items():
        export_path = raw_jsonl_root / filename
        export_jsonl_gz(export_path, repository.fetch_raw_rows(table_name))
        written_paths.append(export_path)

    if args.include_cache:
        cache = ResponseCache()
        cache_root = output_root / "raw" / "cache"
        for entry in cache.list_entries():
            relative = entry.relative_to(cache.cache_root)
            destination = cache_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(entry, destination)
            written_paths.append(destination)

    processed_root = project_root() / "data" / "processed"
    if args.include_processed:
        for filename in PROCESSED_EXPORTS:
            destination = output_root / "processed" / filename
            if copy_if_exists(processed_root / filename, destination):
                written_paths.append(destination)

    reports_root = project_root() / "data" / "artifacts" / "reports"
    if args.include_reports:
        for filename in REPORT_EXPORTS:
            destination = output_root / "reports" / filename
            if copy_if_exists(reports_root / filename, destination):
                written_paths.append(destination)

    checksums = build_checksums_map(output_root, written_paths)
    manifest = build_data_pack_manifest(
        repository,
        data_pack_id=output_root.name,
        pack_root=output_root,
        sources=["rawg", "wikidata", "steam", "wikipedia", "igdb"],
        checksums=checksums,
    )
    manifest_path = write_manifest(output_root / "manifest.json", manifest)
    written_paths.append(manifest_path)
    checksum_path = write_checksums(output_root, written_paths)
    print(
        {
            "output": str(output_root),
            "written_files": len(written_paths),
            "checksum_path": str(checksum_path),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
