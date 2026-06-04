"""Entity resolution blocking helpers."""

from __future__ import annotations


def default_blocking_strategy() -> str:
    return "external_id + normalized_title + year/title token + alias overlap"
