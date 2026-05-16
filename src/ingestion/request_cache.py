"""Minimal request cache placeholder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RequestCache:
    cache_dir: Path

    def cache_path(self, key: str) -> Path:
        safe_key = key.replace("/", "_")
        return self.cache_dir / f"{safe_key}.json"
