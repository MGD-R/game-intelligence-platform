"""Transform Steam appdetails raw payloads into source-normalized staging tables."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.ingestion.repository import IngestionRepository
from src.preprocessing.normalize_flags import infer_flag_set
from src.preprocessing.normalize_text import normalize_title_text

MONTH_NUMBERS = {
    "jan": 1,
    "january": 1,
    "янв": 1,
    "января": 1,
    "feb": 2,
    "february": 2,
    "фев": 2,
    "февраля": 2,
    "mar": 3,
    "march": 3,
    "мар": 3,
    "марта": 3,
    "apr": 4,
    "april": 4,
    "апр": 4,
    "апреля": 4,
    "may": 5,
    "мая": 5,
    "jun": 6,
    "june": 6,
    "июн": 6,
    "июня": 6,
    "jul": 7,
    "july": 7,
    "июл": 7,
    "июля": 7,
    "aug": 8,
    "august": 8,
    "авг": 8,
    "августа": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "сен": 9,
    "сентября": 9,
    "oct": 10,
    "october": 10,
    "окт": 10,
    "октября": 10,
    "nov": 11,
    "november": 11,
    "ноя": 11,
    "ноября": 11,
    "dec": 12,
    "december": 12,
    "дек": 12,
    "декабря": 12,
}


def normalize_description_text(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"\s+", " ", value).strip()
    return normalized or None


def parse_steam_release_date(value: dict[str, Any] | str | None) -> tuple[str | None, int | None]:
    if isinstance(value, dict):
        raw_value = str(value.get("date") or "").strip()
    else:
        raw_value = str(value or "").strip()
    if not raw_value:
        return None, None

    match = re.search(
        r"(?P<day>\d{1,2})\s+(?P<month>[A-Za-zА-Яа-я.]+)\s*,?\s*(?P<year>\d{4})",
        raw_value,
    )
    if match:
        month_key = match.group("month").strip(".").lower()
        month_number = MONTH_NUMBERS.get(month_key)
        if month_number is not None:
            year = int(match.group("year"))
            day = int(match.group("day"))
            return f"{year:04d}-{month_number:02d}-{day:02d}", year

    year_match = re.search(r"(19|20)\d{2}", raw_value)
    if year_match:
        return None, int(year_match.group(0))
    return None, None


def steam_store_url(appid: str) -> str:
    return f"https://store.steampowered.com/app/{appid}/"


def extract_appdetails_data(payload: dict[str, Any], appid: str) -> dict[str, Any] | None:
    app_payload = payload.get(appid)
    if not isinstance(app_payload, dict):
        return None
    if not app_payload.get("success"):
        return None
    data = app_payload.get("data")
    return data if isinstance(data, dict) else None


def extract_platform_names(payload: dict[str, Any]) -> list[str]:
    platforms = payload.get("platforms", {})
    if not isinstance(platforms, dict):
        return []
    names: list[str] = []
    for name in ("windows", "mac", "linux"):
        if platforms.get(name):
            names.append(name)
    return names


def extract_genre_names(payload: dict[str, Any]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for item in payload.get("genres", []) or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("description") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def extract_tag_names(payload: dict[str, Any]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for item in payload.get("categories", []) or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("description") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def steam_company_rows(payload: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for role, key in (("developer", "developers"), ("publisher", "publishers")):
        seen: set[str] = set()
        for item in payload.get(key, []) or []:
            name = str(item or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            rows.append({"company_name": name, "company_role": role})
    return rows


def steam_description_rows(payload: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for description_type in (
        "short_description",
        "detailed_description",
        "about_the_game",
    ):
        text = normalize_description_text(str(payload.get(description_type) or ""))
        if not text:
            continue
        rows.append(
            {
                "description_type": description_type,
                "language": "ru",
                "description_text": text,
                "source_url": payload.get("website")
                or steam_store_url(str(payload["steam_appid"])),
            }
        )
    return rows


def steam_rating_rows(payload: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    metacritic = payload.get("metacritic")
    if isinstance(metacritic, dict) and metacritic.get("score") is not None:
        rows.append(
            {
                "rating_type": "steam_metacritic",
                "rating_value": metacritic.get("score"),
                "rating_scale": "100",
                "rating_count": None,
            }
        )
    return rows


def steam_popularity_rows(payload: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    recommendations = payload.get("recommendations")
    if isinstance(recommendations, dict) and recommendations.get("total") is not None:
        rows.append(
            {
                "metric_name": "recommendations_total",
                "metric_value": recommendations.get("total"),
                "metric_unit": "count",
            }
        )
    return rows


def steam_url_rows(payload: dict[str, Any], appid: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = [("store_url", steam_store_url(appid))]
    for url_type in ("website", "header_image"):
        value = str(payload.get(url_type) or "").strip()
        if value:
            rows.append((url_type, value))
    return rows


@dataclass(slots=True)
class SteamStagingBundle:
    source_games: list[dict[str, object]] = field(default_factory=list)
    source_game_genres: list[dict[str, object]] = field(default_factory=list)
    source_game_tags: list[dict[str, object]] = field(default_factory=list)
    source_game_platforms: list[dict[str, object]] = field(default_factory=list)
    source_game_companies: list[dict[str, object]] = field(default_factory=list)
    source_game_descriptions: list[dict[str, object]] = field(default_factory=list)
    source_game_ratings: list[dict[str, object]] = field(default_factory=list)
    source_game_popularity: list[dict[str, object]] = field(default_factory=list)
    source_game_urls: list[dict[str, object]] = field(default_factory=list)
    source_game_external_ids: list[dict[str, object]] = field(default_factory=list)


def transform_steam_payloads(
    raw_payloads: list[tuple[str, dict[str, Any], str]],
) -> SteamStagingBundle:
    now = datetime.now(UTC).isoformat()
    bundle = SteamStagingBundle()

    for appid, payload, loaded_at in raw_payloads:
        data = extract_appdetails_data(payload, appid)
        if data is None:
            continue
        name = str(data.get("name") or appid)
        release_date, release_year = parse_steam_release_date(data.get("release_date"))
        inferred_flags, flag_reasons = infer_flag_set({"name": name})
        app_type = str(data.get("type") or "").lower()
        categories = extract_tag_names(data)
        bundle.source_games.append(
            {
                "source": "steam",
                "source_game_id": appid,
                "name": name,
                "name_normalized": normalize_title_text(name),
                "release_date": release_date,
                "release_year": release_year,
                "slug": appid,
                "game_type": str(data.get("type") or "") or None,
                "is_dlc": app_type == "dlc" or inferred_flags["is_dlc"],
                "is_demo": app_type == "demo" or inferred_flags["is_demo"],
                "is_remake": inferred_flags["is_remake"],
                "is_remaster": inferred_flags["is_remaster"],
                "is_bundle": inferred_flags["is_bundle"],
                "raw_loaded_at": loaded_at,
                "stg_loaded_at": now,
                "source_priority": 60,
                "quality_flags_json": {
                    "has_supported_languages": bool(data.get("supported_languages")),
                    "has_recommendations": isinstance(data.get("recommendations"), dict)
                    and data["recommendations"].get("total") is not None,
                    "has_metacritic": isinstance(data.get("metacritic"), dict)
                    and data["metacritic"].get("score") is not None,
                    "is_free": bool(data.get("is_free")),
                    "required_age": data.get("required_age"),
                    "controller_support": data.get("controller_support"),
                    "category_count": len(categories),
                    **{reason: True for reason in flag_reasons},
                },
            }
        )
        bundle.source_game_external_ids.append(
            {
                "source": "steam",
                "source_game_id": appid,
                "external_source": "steam",
                "external_id": appid,
                "confidence": 1.0,
                "source_specific_json": {"match_type": "steam_self_id"},
                "stg_loaded_at": now,
            }
        )

        for genre_name in extract_genre_names(data):
            bundle.source_game_genres.append(
                {
                    "source": "steam",
                    "source_game_id": appid,
                    "genre_name": genre_name,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                }
            )
        for tag_name in categories:
            bundle.source_game_tags.append(
                {
                    "source": "steam",
                    "source_game_id": appid,
                    "tag_name": tag_name,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                }
            )
        for platform_name in extract_platform_names(data):
            bundle.source_game_platforms.append(
                {
                    "source": "steam",
                    "source_game_id": appid,
                    "platform_name": platform_name,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                }
            )
        for row in steam_company_rows(data):
            bundle.source_game_companies.append(
                {
                    "source": "steam",
                    "source_game_id": appid,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                    **row,
                }
            )
        for row in steam_description_rows(data):
            bundle.source_game_descriptions.append(
                {
                    "source": "steam",
                    "source_game_id": appid,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                    **row,
                }
            )
        for row in steam_rating_rows(data):
            bundle.source_game_ratings.append(
                {
                    "source": "steam",
                    "source_game_id": appid,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                    **row,
                }
            )
        for row in steam_popularity_rows(data):
            bundle.source_game_popularity.append(
                {
                    "source": "steam",
                    "source_game_id": appid,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                    **row,
                }
            )
        for url_type, url in steam_url_rows(data, appid):
            bundle.source_game_urls.append(
                {
                    "source": "steam",
                    "source_game_id": appid,
                    "url_type": url_type,
                    "url": url,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                }
            )

    return bundle


def load_steam_payloads(
    repository: IngestionRepository,
) -> list[tuple[str, dict[str, Any], str]]:
    rows = repository.fetch_raw_rows("raw.steam_app_details")
    payloads: list[tuple[str, dict[str, Any], str]] = []
    for row in rows:
        response_json = row.get("response_json")
        source_record_id = row.get("source_record_id")
        if not isinstance(response_json, dict) or source_record_id is None:
            continue
        payloads.append((str(source_record_id), response_json, str(row.get("loaded_at"))))
    return payloads


def write_bundle(repository: IngestionRepository, bundle: SteamStagingBundle) -> None:
    repository.replace_source_staging_rows(
        source="steam",
        table_name="stg.source_games",
        rows=bundle.source_games,
        key_columns=["source", "source_game_id"],
    )
    repository.replace_source_staging_rows(
        source="steam",
        table_name="stg.source_game_genres",
        rows=bundle.source_game_genres,
        key_columns=["source", "source_game_id", "genre_name"],
    )
    repository.replace_source_staging_rows(
        source="steam",
        table_name="stg.source_game_tags",
        rows=bundle.source_game_tags,
        key_columns=["source", "source_game_id", "tag_name"],
    )
    repository.replace_source_staging_rows(
        source="steam",
        table_name="stg.source_game_platforms",
        rows=bundle.source_game_platforms,
        key_columns=["source", "source_game_id", "platform_name"],
    )
    repository.replace_source_staging_rows(
        source="steam",
        table_name="stg.source_game_companies",
        rows=bundle.source_game_companies,
        key_columns=["source", "source_game_id", "company_name", "company_role"],
    )
    repository.replace_source_staging_rows(
        source="steam",
        table_name="stg.source_game_descriptions",
        rows=bundle.source_game_descriptions,
        key_columns=["source", "source_game_id", "description_type"],
    )
    repository.replace_source_staging_rows(
        source="steam",
        table_name="stg.source_game_ratings",
        rows=bundle.source_game_ratings,
        key_columns=["source", "source_game_id", "rating_type"],
    )
    repository.replace_source_staging_rows(
        source="steam",
        table_name="stg.source_game_popularity",
        rows=bundle.source_game_popularity,
        key_columns=["source", "source_game_id", "metric_name"],
    )
    repository.replace_source_staging_rows(
        source="steam",
        table_name="stg.source_game_urls",
        rows=bundle.source_game_urls,
        key_columns=["source", "source_game_id", "url_type", "url"],
    )
    repository.replace_source_staging_rows(
        source="steam",
        table_name="stg.source_game_external_ids",
        rows=bundle.source_game_external_ids,
        key_columns=["source", "source_game_id", "external_source", "external_id"],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Transform Steam appdetails into staging rows.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview staging targets without DB reads or writes.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run:
        print(
            {
                "source": "steam",
                "raw_table": "raw.steam_app_details",
                "target_tables": [
                    "stg.source_games",
                    "stg.source_game_genres",
                    "stg.source_game_tags",
                    "stg.source_game_platforms",
                    "stg.source_game_companies",
                    "stg.source_game_descriptions",
                    "stg.source_game_ratings",
                    "stg.source_game_popularity",
                    "stg.source_game_urls",
                    "stg.source_game_external_ids",
                ],
            }
        )
        return 0

    repository = IngestionRepository()
    payloads = load_steam_payloads(repository)
    if not payloads:
        raise RuntimeError("Steam raw appdetails are empty. Run `make steam-details` first.")
    bundle = transform_steam_payloads(payloads)
    write_bundle(repository, bundle)
    print(
        {
            "source_games": len(bundle.source_games),
            "descriptions": len(bundle.source_game_descriptions),
            "ratings": len(bundle.source_game_ratings),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
