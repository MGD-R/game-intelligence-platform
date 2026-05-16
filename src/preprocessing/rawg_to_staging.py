"""Transform RAWG raw tables into source-normalized staging tables."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.ingestion.repository import IngestionRepository


def normalize_name(name: str | None) -> str | None:
    if not name:
        return None
    normalized = re.sub(r"[^a-z0-9]+", " ", name.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def extract_platform_names(payload: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in payload.get("platforms", []) or []:
        if isinstance(item, dict):
            platform = item.get("platform", item)
            if isinstance(platform, dict) and platform.get("name"):
                names.append(str(platform["name"]))
    return names


def extract_tag_names(payload: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []
    for item in payload.get("tags", []) or []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        name = str(item["name"])
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def extract_genre_names(payload: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []
    for item in payload.get("genres", []) or []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        name = str(item["name"])
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def infer_game_type(payload: dict[str, Any]) -> str | None:
    if payload.get("tba"):
        return "tba"
    if payload.get("type"):
        return str(payload["type"])
    if payload.get("esrb_rating") and isinstance(payload["esrb_rating"], dict):
        return "game"
    return None


def rawg_urls(payload: dict[str, Any]) -> list[tuple[str, str]]:
    urls: list[tuple[str, str]] = []
    for url_type in ("website", "background_image", "reddit_url", "metacritic_url"):
        value = payload.get(url_type)
        if value:
            urls.append((url_type, str(value)))
    metacritic = payload.get("metacritic")
    if metacritic and not any(item[0] == "metacritic_url" for item in urls):
        slug = payload.get("slug")
        if slug:
            urls.append(("metacritic_url", f"https://www.metacritic.com/game/{slug}"))
    return urls


def rawg_description_rows(payload: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    text = payload.get("description_raw") or payload.get("description")
    if text:
        rows.append(
            {
                "description_type": "summary",
                "language": "en",
                "description_text": str(text),
                "source_url": payload.get("website"),
            }
        )
    return rows


def rawg_company_rows(payload: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for role, key in (("developer", "developers"), ("publisher", "publishers")):
        for item in payload.get(key, []) or []:
            if isinstance(item, dict) and item.get("name"):
                rows.append({"company_name": str(item["name"]), "company_role": role})
    return rows


def rawg_rating_rows(payload: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if payload.get("rating") is not None:
        rows.append(
            {
                "rating_type": "rawg_rating",
                "rating_value": payload.get("rating"),
                "rating_scale": "5",
                "rating_count": payload.get("ratings_count"),
            }
        )
    if payload.get("rating_top") is not None:
        rows.append(
            {
                "rating_type": "rawg_rating_top",
                "rating_value": payload.get("rating_top"),
                "rating_scale": "5",
                "rating_count": payload.get("ratings_count"),
            }
        )
    if payload.get("metacritic") is not None:
        rows.append(
            {
                "rating_type": "rawg_metacritic",
                "rating_value": payload.get("metacritic"),
                "rating_scale": "100",
                "rating_count": None,
            }
        )
    return rows


def rawg_popularity_rows(payload: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if payload.get("playtime") is not None:
        rows.append(
            {
                "metric_name": "playtime_hours",
                "metric_value": payload.get("playtime"),
                "metric_unit": "hours",
            }
        )
    return rows


@dataclass(slots=True)
class RawgStagingBundle:
    source_games: list[dict[str, object]] = field(default_factory=list)
    source_game_genres: list[dict[str, object]] = field(default_factory=list)
    source_game_platforms: list[dict[str, object]] = field(default_factory=list)
    source_game_tags: list[dict[str, object]] = field(default_factory=list)
    source_game_companies: list[dict[str, object]] = field(default_factory=list)
    source_game_descriptions: list[dict[str, object]] = field(default_factory=list)
    source_game_ratings: list[dict[str, object]] = field(default_factory=list)
    source_game_urls: list[dict[str, object]] = field(default_factory=list)
    source_game_popularity: list[dict[str, object]] = field(default_factory=list)


def transform_rawg_payloads(
    index_payloads: list[tuple[dict[str, Any], str]],
    details_payloads: dict[str, tuple[dict[str, Any], str]],
) -> RawgStagingBundle:
    now = datetime.now(UTC).isoformat()
    games_by_id: dict[str, dict[str, Any]] = {}
    raw_loaded_at_by_id: dict[str, str] = {}

    for payload, loaded_at in index_payloads:
        for item in payload.get("results", []) or []:
            if isinstance(item, dict) and item.get("id") is not None:
                game_id = str(item["id"])
                games_by_id[game_id] = dict(item)
                raw_loaded_at_by_id[game_id] = loaded_at

    for game_id, (details, loaded_at) in details_payloads.items():
        merged = dict(games_by_id.get(game_id, {}))
        merged.update(details)
        games_by_id[game_id] = merged
        raw_loaded_at_by_id[game_id] = loaded_at

    bundle = RawgStagingBundle()
    for game_id, payload in sorted(games_by_id.items()):
        release_date = payload.get("released")
        release_year = int(str(release_date)[:4]) if release_date else None
        has_details = game_id in details_payloads
        bundle.source_games.append(
            {
                "source": "rawg",
                "source_game_id": game_id,
                "name": str(payload.get("name") or ""),
                "name_normalized": normalize_name(payload.get("name")),
                "release_date": release_date,
                "release_year": release_year,
                "slug": payload.get("slug"),
                "game_type": infer_game_type(payload),
                "is_dlc": False,
                "is_demo": False,
                "is_remake": False,
                "is_remaster": False,
                "is_bundle": False,
                "raw_loaded_at": raw_loaded_at_by_id.get(game_id),
                "stg_loaded_at": now,
                "source_priority": 100,
                "quality_flags_json": {"has_details": has_details},
            }
        )

        for genre_name in extract_genre_names(payload):
            bundle.source_game_genres.append(
                {
                    "source": "rawg",
                    "source_game_id": game_id,
                    "genre_name": genre_name,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                }
            )

        for platform_name in extract_platform_names(payload):
            bundle.source_game_platforms.append(
                {
                    "source": "rawg",
                    "source_game_id": game_id,
                    "platform_name": platform_name,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                }
            )

        for tag_name in extract_tag_names(payload):
            bundle.source_game_tags.append(
                {
                    "source": "rawg",
                    "source_game_id": game_id,
                    "tag_name": tag_name,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                }
            )

        for row in rawg_company_rows(payload):
            bundle.source_game_companies.append(
                {
                    "source": "rawg",
                    "source_game_id": game_id,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                    **row,
                }
            )

        for row in rawg_description_rows(payload):
            bundle.source_game_descriptions.append(
                {
                    "source": "rawg",
                    "source_game_id": game_id,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                    **row,
                }
            )

        for row in rawg_rating_rows(payload):
            bundle.source_game_ratings.append(
                {
                    "source": "rawg",
                    "source_game_id": game_id,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                    **row,
                }
            )

        for row in rawg_popularity_rows(payload):
            bundle.source_game_popularity.append(
                {
                    "source": "rawg",
                    "source_game_id": game_id,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                    **row,
                }
            )

        for url_type, url in rawg_urls(payload):
            bundle.source_game_urls.append(
                {
                    "source": "rawg",
                    "source_game_id": game_id,
                    "url_type": url_type,
                    "url": url,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                }
            )

    return bundle


def load_rawg_payloads(
    repository: IngestionRepository,
) -> tuple[list[tuple[dict[str, Any], str]], dict[str, tuple[dict[str, Any], str]]]:
    index_rows = repository.fetch_raw_rows("raw.rawg_game_index")
    details_rows = repository.fetch_raw_rows("raw.rawg_game_details")
    index_payloads = [
        (row.get("response_json") or {}, str(row.get("loaded_at")))
        for row in index_rows
        if isinstance(row.get("response_json"), dict)
    ]
    details_payloads = {
        str(row.get("source_record_id")): (
            row.get("response_json") or {},
            str(row.get("loaded_at")),
        )
        for row in details_rows
        if isinstance(row.get("response_json"), dict) and row.get("source_record_id") is not None
    }
    return index_payloads, details_payloads


def write_bundle(repository: IngestionRepository, bundle: RawgStagingBundle) -> None:
    repository.replace_source_staging_rows(
        source="rawg",
        table_name="stg.source_games",
        rows=bundle.source_games,
        key_columns=["source", "source_game_id"],
    )
    repository.replace_source_staging_rows(
        source="rawg",
        table_name="stg.source_game_genres",
        rows=bundle.source_game_genres,
        key_columns=["source", "source_game_id", "genre_name"],
    )
    repository.replace_source_staging_rows(
        source="rawg",
        table_name="stg.source_game_platforms",
        rows=bundle.source_game_platforms,
        key_columns=["source", "source_game_id", "platform_name"],
    )
    repository.replace_source_staging_rows(
        source="rawg",
        table_name="stg.source_game_tags",
        rows=bundle.source_game_tags,
        key_columns=["source", "source_game_id", "tag_name"],
    )
    repository.replace_source_staging_rows(
        source="rawg",
        table_name="stg.source_game_companies",
        rows=bundle.source_game_companies,
        key_columns=["source", "source_game_id", "company_name", "company_role"],
    )
    repository.replace_source_staging_rows(
        source="rawg",
        table_name="stg.source_game_descriptions",
        rows=bundle.source_game_descriptions,
        key_columns=["source", "source_game_id", "description_type", "language"],
    )
    repository.replace_source_staging_rows(
        source="rawg",
        table_name="stg.source_game_ratings",
        rows=bundle.source_game_ratings,
        key_columns=["source", "source_game_id", "rating_type"],
    )
    repository.replace_source_staging_rows(
        source="rawg",
        table_name="stg.source_game_urls",
        rows=bundle.source_game_urls,
        key_columns=["source", "source_game_id", "url_type", "url"],
    )
    repository.replace_source_staging_rows(
        source="rawg",
        table_name="stg.source_game_popularity",
        rows=bundle.source_game_popularity,
        key_columns=["source", "source_game_id", "metric_name"],
    )


def main() -> int:
    repository = IngestionRepository()
    index_payloads, details_payloads = load_rawg_payloads(repository)
    bundle = transform_rawg_payloads(index_payloads, details_payloads)
    write_bundle(repository, bundle)
    print(
        {
            "source_games": len(bundle.source_games),
            "genres": len(bundle.source_game_genres),
            "platforms": len(bundle.source_game_platforms),
            "tags": len(bundle.source_game_tags),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
