"""File-based response cache for ingestion requests."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.utils.config import project_root


@dataclass(slots=True)
class ResponseCache:
    cache_root: Path = field(default_factory=lambda: project_root() / "data" / "raw" / "cache")

    def source_dir(self, source: str) -> Path:
        return self.cache_root / source

    def cache_path(self, source: str, request_hash: str) -> Path:
        return self.source_dir(source) / f"{request_hash}.json"

    def exists(self, source: str, request_hash: str) -> bool:
        return self.cache_path(source, request_hash).exists()

    def read(self, source: str, request_hash: str) -> dict[str, Any]:
        path = self.cache_path(source, request_hash)
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def write(self, source: str, request_hash: str, payload: dict[str, Any]) -> Path:
        path = self.cache_path(source, request_hash)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
        return path

    def list_entries(self, source: str | None = None) -> list[Path]:
        if source:
            return sorted(self.source_dir(source).glob("*.json"))
        return sorted(self.cache_root.glob("*/*.json"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect ingestion cache entries.")
    parser.add_argument("--list", action="store_true", help="List cache entry paths.")
    parser.add_argument("--source", help="Optional source name filter.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cache = ResponseCache()
    if args.list:
        entries = cache.list_entries(args.source)
        if not entries:
            print("Cache entries: none")
        else:
            print("Cache entries:")
            for entry in entries:
                print(entry)
        return 0

    print("Use --list to inspect cache entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
