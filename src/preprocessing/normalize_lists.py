"""List normalization helpers for staging features and reporting."""

from __future__ import annotations

from src.preprocessing.normalize_text import normalize_title_text


def normalize_string_list(values: list[str] | set[str] | tuple[str, ...]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = normalize_title_text(value)
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized
