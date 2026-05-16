"""Conservative flag normalization helpers."""

from __future__ import annotations

from typing import Any

from src.preprocessing.normalize_text import normalize_title_text


def infer_flag_set(payload: dict[str, Any]) -> tuple[dict[str, bool], list[str]]:
    title = normalize_title_text(str(payload.get("name") or "")) or ""
    quality_flags: list[str] = []

    def has_any(*tokens: str) -> bool:
        return any(token in title for token in tokens)

    flags = {
        "is_dlc": has_any(" dlc ", " expansion ", " add on ", " addon "),
        "is_demo": has_any(" demo ", " trial "),
        "is_remake": has_any(" remake "),
        "is_remaster": has_any(" remaster ", " remastered "),
        "is_bundle": has_any(" bundle ", " collection ", " anthology "),
    }

    for key, value in flags.items():
        if not value:
            quality_flags.append(f"{key}_not_inferred")
    return flags, quality_flags
