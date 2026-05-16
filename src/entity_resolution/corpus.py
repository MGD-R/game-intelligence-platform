"""Reusable source record corpus helpers for deterministic candidate generation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from src.ingestion.repository import IngestionRepository


def normalize_text(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return re.sub(r"\s+", " ", normalized).strip() or None


def text_similarity(left: str | None, right: str | None) -> float | None:
    if not left or not right:
        return None
    return round(SequenceMatcher(None, left, right).ratio(), 6)


def jaccard_similarity(left: set[str], right: set[str]) -> float | None:
    if not left or not right:
        return None
    union = left | right
    if not union:
        return None
    return round(len(left & right) / len(union), 6)


@dataclass(slots=True)
class SourceGameRecord:
    source: str
    source_game_id: str
    name: str
    name_normalized: str | None
    release_year: int | None
    aliases: set[str] = field(default_factory=set)
    alias_languages: dict[str, set[str]] = field(default_factory=dict)
    external_ids: dict[str, str] = field(default_factory=dict)
    genres: set[str] = field(default_factory=set)
    platforms: set[str] = field(default_factory=set)
    tags: set[str] = field(default_factory=set)
    developers: set[str] = field(default_factory=set)
    publishers: set[str] = field(default_factory=set)
    url_types: set[str] = field(default_factory=set)
    has_description: bool = False

    @property
    def comparison_names(self) -> set[str]:
        values = {value for value in {self.name_normalized, *self.aliases} if value}
        return values

    @property
    def first_name_token(self) -> str | None:
        if not self.name_normalized:
            return None
        return self.name_normalized.split()[0]


def _ensure_record(records: dict[tuple[str, str], SourceGameRecord], row: dict[str, Any]) -> None:
    key = (str(row["source"]), str(row["source_game_id"]))
    if key in records:
        return
    records[key] = SourceGameRecord(
        source=str(row["source"]),
        source_game_id=str(row["source_game_id"]),
        name=str(row["name"]),
        name_normalized=(str(row["name_normalized"]) if row.get("name_normalized") else None),
        release_year=int(row["release_year"]) if row.get("release_year") is not None else None,
    )


def load_source_records(repository: IngestionRepository) -> dict[tuple[str, str], SourceGameRecord]:
    records: dict[tuple[str, str], SourceGameRecord] = {}

    for row in repository.fetch_staging_rows("stg.source_games"):
        _ensure_record(records, row)

    for row in repository.fetch_staging_rows("stg.source_game_aliases"):
        key = (str(row["source"]), str(row["source_game_id"]))
        record = records.get(key)
        if record is None:
            continue
        alias_normalized = normalize_text(str(row["alias"]))
        if alias_normalized:
            record.aliases.add(alias_normalized)
            language = str(row["language"]) if row.get("language") else "unknown"
            record.alias_languages.setdefault(language, set()).add(alias_normalized)

    for row in repository.fetch_staging_rows("stg.source_game_external_ids"):
        key = (str(row["source"]), str(row["source_game_id"]))
        record = records.get(key)
        if record is None:
            continue
        record.external_ids[str(row["external_source"])] = str(row["external_id"])

    for row in repository.fetch_staging_rows("stg.source_game_genres"):
        key = (str(row["source"]), str(row["source_game_id"]))
        record = records.get(key)
        if record is not None:
            normalized = normalize_text(str(row["genre_name"]))
            if normalized:
                record.genres.add(normalized)

    for row in repository.fetch_staging_rows("stg.source_game_platforms"):
        key = (str(row["source"]), str(row["source_game_id"]))
        record = records.get(key)
        if record is not None:
            normalized = normalize_text(str(row["platform_name"]))
            if normalized:
                record.platforms.add(normalized)

    for row in repository.fetch_staging_rows("stg.source_game_tags"):
        key = (str(row["source"]), str(row["source_game_id"]))
        record = records.get(key)
        if record is not None:
            normalized = normalize_text(str(row["tag_name"]))
            if normalized:
                record.tags.add(normalized)

    for row in repository.fetch_staging_rows("stg.source_game_companies"):
        key = (str(row["source"]), str(row["source_game_id"]))
        record = records.get(key)
        if record is None:
            continue
        normalized = normalize_text(str(row["company_name"]))
        if not normalized:
            continue
        role = str(row["company_role"])
        if role == "developer":
            record.developers.add(normalized)
        elif role == "publisher":
            record.publishers.add(normalized)

    for row in repository.fetch_staging_rows("stg.source_game_descriptions"):
        key = (str(row["source"]), str(row["source_game_id"]))
        record = records.get(key)
        if record is not None and row.get("description_text"):
            record.has_description = True

    for row in repository.fetch_staging_rows("stg.source_game_urls"):
        key = (str(row["source"]), str(row["source_game_id"]))
        record = records.get(key)
        if record is not None and row.get("url_type"):
            record.url_types.add(str(row["url_type"]))

    return records
