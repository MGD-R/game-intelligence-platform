"""Text normalization helpers for staging-level analytical fields."""

from __future__ import annotations

import re

TRADEMARK_PATTERN = re.compile(r"[®™©]")
PUNCTUATION_PATTERN = re.compile(r"[\s:;,_./\\|()\[\]{}!?+'\"-]+")
WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_title_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip().lower()
    if not text:
        return None
    text = TRADEMARK_PATTERN.sub("", text)
    text = PUNCTUATION_PATTERN.sub(" ", text)
    text = WHITESPACE_PATTERN.sub(" ", text).strip()
    return text or None


def normalize_description_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = WHITESPACE_PATTERN.sub(" ", value.strip())
    return text or None
