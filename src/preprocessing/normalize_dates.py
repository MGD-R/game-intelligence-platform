"""Safe date parsing helpers for staging normalization."""

from __future__ import annotations

from datetime import date


def normalize_release_date(value: str | None) -> tuple[str | None, int | None, str | None]:
    if not value:
        return None, None, "missing_release_date"
    text = value.strip()
    if not text:
        return None, None, "missing_release_date"
    if len(text) >= 10:
        candidate = text[:10]
        try:
            parsed = date.fromisoformat(candidate)
            return parsed.isoformat(), parsed.year, None
        except ValueError:
            pass
    if len(text) >= 4 and text[:4].isdigit():
        return None, int(text[:4]), "partial_release_date"
    return None, None, "invalid_release_date"
