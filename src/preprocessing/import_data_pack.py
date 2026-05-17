"""Import file-based data packs into the local database and cache."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
from pathlib import Path

from src.ingestion.repository import IngestionRepository
from src.ingestion.request_cache import ResponseCache
from src.preprocessing.data_pack_manifest import RAW_TABLE_EXPORTS, checksum_for_file
from src.utils.config import project_root


def _read_jsonl_gz(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def verify_checksums(pack_root: Path) -> None:
    checksum_path = pack_root / "checksums.sha256"
    if not checksum_path.exists():
        return
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", maxsplit=1)
        file_path = pack_root / relative
        if not file_path.exists():
            raise RuntimeError(f"Missing checksum target: {relative}")
        actual = checksum_for_file(file_path)
        if actual != expected:
            raise RuntimeError(f"Checksum mismatch for {relative}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import a local data pack.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--raw-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_root = Path(args.input)
    if not input_root.exists():
        raise RuntimeError(f"Data pack does not exist: {input_root}")

    verify_checksums(input_root)
    manifest_path = input_root / "manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    )

    if args.dry_run:
        print(
            {
                "input": str(input_root),
                "raw_only": args.raw_only,
                "manifest": manifest.get("data_pack_id"),
            }
        )
        return 0

    repository = IngestionRepository()
    imported_counts: dict[str, int] = {}
    for table_name, filename in RAW_TABLE_EXPORTS.items():
        path = input_root / "raw" / "jsonl" / filename
        if not path.exists():
            continue
        rows = _read_jsonl_gz(path)
        for row in rows:
            repository.import_raw_record(table_name=table_name, row=row)
        imported_counts[table_name] = len(rows)

    if not args.raw_only:
        cache_root = input_root / "raw" / "cache"
        if cache_root.exists():
            cache = ResponseCache()
            for entry in cache_root.rglob("*.json"):
                destination = cache.cache_root / entry.relative_to(cache_root)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(entry, destination)
        for subdir in ("processed", "reports"):
            source_dir = input_root / subdir
            if not source_dir.exists():
                continue
            if subdir == "processed":
                target_dir = project_root() / "data" / "processed"
            else:
                target_dir = project_root() / "data" / "artifacts" / "reports"
            for file_path in source_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                destination = target_dir / file_path.relative_to(source_dir)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, destination)

    print({"input": str(input_root), "imported_counts": imported_counts})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
