"""Transform IGDB raw payloads into source-normalized staging tables."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.ingestion.repository import IngestionRepository
from src.preprocessing.normalize_flags import infer_flag_set
from src.preprocessing.normalize_text import normalize_title_text


def parse_unix_date(value: object) -> tuple[str | None, int | None]:
    if value in (None, ""):
        return None, None
    try:
        dt = datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None, None
    return dt.date().isoformat(), dt.year


def _extract_names(items: object, key: str = "name") -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    if not isinstance(items, list):
        return names
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get(key) or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def _extract_company_rows(items: object) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    if not isinstance(items, list):
        return rows
    for item in items:
        if not isinstance(item, dict):
            continue
        company = item.get("company")
        company_name = str(company.get("name") or "").strip() if isinstance(company, dict) else ""
        if not company_name:
            continue
        for role_name in ("developer", "publisher", "porting", "supporting"):
            if item.get(role_name):
                key = (company_name, role_name)
                if key in seen:
                    continue
                seen.add(key)
                rows.append({"company_name": company_name, "company_role": role_name})
    return rows


def _extract_external_ids(items: object, game_id: str, now: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "source": "igdb",
            "source_game_id": game_id,
            "external_source": "igdb",
            "external_id": game_id,
            "confidence": 1.0,
            "source_specific_json": {"match_type": "igdb_self_id"},
            "stg_loaded_at": now,
        }
    ]
    if not isinstance(items, list):
        return rows
    for item in items:
        if not isinstance(item, dict):
            continue
        source_info = item.get("external_game_source")
        source_name = (
            str(source_info.get("name") or "").strip().lower()
            if isinstance(source_info, dict)
            else ""
        )
        external_id = str(item.get("uid") or "").strip()
        if not source_name or not external_id:
            continue
        rows.append(
            {
                "source": "igdb",
                "source_game_id": game_id,
                "external_source": source_name,
                "external_id": external_id,
                "confidence": 0.9,
                "source_specific_json": {"category": item.get("category")},
                "stg_loaded_at": now,
            }
        )
    return rows


def _extract_url_rows(items: object, game_id: str, now: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    if not isinstance(items, list):
        return rows
    for item in items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        url_type = str(item.get("category") or "website").lower()
        key = (url_type, url)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "source": "igdb",
                "source_game_id": game_id,
                "url_type": url_type,
                "url": url,
                "source_specific_json": {},
                "stg_loaded_at": now,
            }
        )
    return rows


@dataclass(slots=True)
class IGDBStagingBundle:
    source_games: list[dict[str, object]] = field(default_factory=list)
    source_game_aliases: list[dict[str, object]] = field(default_factory=list)
    source_game_external_ids: list[dict[str, object]] = field(default_factory=list)
    source_game_genres: list[dict[str, object]] = field(default_factory=list)
    source_game_tags: list[dict[str, object]] = field(default_factory=list)
    source_game_themes: list[dict[str, object]] = field(default_factory=list)
    source_game_platforms: list[dict[str, object]] = field(default_factory=list)
    source_game_companies: list[dict[str, object]] = field(default_factory=list)
    source_game_descriptions: list[dict[str, object]] = field(default_factory=list)
    source_game_ratings: list[dict[str, object]] = field(default_factory=list)
    source_game_popularity: list[dict[str, object]] = field(default_factory=list)
    source_game_urls: list[dict[str, object]] = field(default_factory=list)


def transform_igdb_payloads(raw_payloads: list[tuple[dict[str, Any], str]]) -> IGDBStagingBundle:
    bundle = IGDBStagingBundle()
    now = datetime.now(UTC).isoformat()
    for payload, loaded_at in raw_payloads:
        game_id = str(payload.get("id") or "").strip()
        if not game_id:
            continue
        name = str(payload.get("name") or game_id)
        release_date, release_year = parse_unix_date(payload.get("first_release_date"))
        inferred_flags, flag_reasons = infer_flag_set(
            {"name": name, "version_title": payload.get("version_title")}
        )
        bundle.source_games.append(
            {
                "source": "igdb",
                "source_game_id": game_id,
                "name": name,
                "name_normalized": normalize_title_text(name),
                "release_date": release_date,
                "release_year": release_year,
                "slug": str(payload.get("slug") or "") or None,
                "game_type": str(payload.get("game_type") or "") or None,
                "is_dlc": inferred_flags["is_dlc"],
                "is_demo": inferred_flags["is_demo"],
                "is_remake": False,
                "is_remaster": False,
                "is_bundle": False,
                "raw_loaded_at": loaded_at,
                "stg_loaded_at": now,
                "source_priority": 55,
                "quality_flags_json": {
                    "has_themes": bool(payload.get("themes")),
                    "has_keywords": bool(payload.get("keywords")),
                    "has_localizations": bool(payload.get("game_localizations")),
                    "has_version_parent": payload.get("version_parent") is not None,
                    **{reason: True for reason in flag_reasons},
                },
            }
        )
        for alias in _extract_names(payload.get("alternative_names")):
            bundle.source_game_aliases.append(
                {
                    "source": "igdb",
                    "source_game_id": game_id,
                    "alias": alias,
                    "language": None,
                    "alias_type": "igdb_alternative_name",
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                }
            )
        for alias in _extract_names(payload.get("game_localizations")):
            bundle.source_game_aliases.append(
                {
                    "source": "igdb",
                    "source_game_id": game_id,
                    "alias": alias,
                    "language": None,
                    "alias_type": "igdb_localization",
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                }
            )
        bundle.source_game_external_ids.extend(
            _extract_external_ids(payload.get("external_games"), game_id, now)
        )
        for genre_name in _extract_names(payload.get("genres")):
            bundle.source_game_genres.append(
                {
                    "source": "igdb",
                    "source_game_id": game_id,
                    "genre_name": genre_name,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                }
            )
        for tag_name in _extract_names(payload.get("keywords")):
            bundle.source_game_tags.append(
                {
                    "source": "igdb",
                    "source_game_id": game_id,
                    "tag_name": tag_name,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                }
            )
        for theme_name in _extract_names(payload.get("themes")):
            bundle.source_game_themes.append(
                {
                    "source": "igdb",
                    "source_game_id": game_id,
                    "theme_name": theme_name,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                }
            )
        for platform_name in _extract_names(payload.get("platforms")):
            bundle.source_game_platforms.append(
                {
                    "source": "igdb",
                    "source_game_id": game_id,
                    "platform_name": platform_name,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                }
            )
        for row in _extract_company_rows(payload.get("involved_companies")):
            bundle.source_game_companies.append(
                {
                    "source": "igdb",
                    "source_game_id": game_id,
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                    **row,
                }
            )
        for description_type in ("summary", "storyline"):
            description = str(payload.get(description_type) or "").strip()
            if description:
                bundle.source_game_descriptions.append(
                    {
                        "source": "igdb",
                        "source_game_id": game_id,
                        "description_type": description_type,
                        "language": None,
                        "description_text": description,
                        "source_url": None,
                        "source_specific_json": {},
                        "stg_loaded_at": now,
                    }
                )
        for rating_key, rating_type in (
            ("rating", "igdb_rating"),
            ("aggregated_rating", "igdb_aggregated_rating"),
            ("total_rating", "igdb_total_rating"),
        ):
            rating_value = payload.get(rating_key)
            if rating_value is None:
                continue
            count_key = f"{rating_key}_count"
            bundle.source_game_ratings.append(
                {
                    "source": "igdb",
                    "source_game_id": game_id,
                    "rating_type": rating_type,
                    "rating_value": rating_value,
                    "rating_scale": "100",
                    "rating_count": payload.get(count_key),
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                }
            )
        if payload.get("updated_at") is not None:
            bundle.source_game_popularity.append(
                {
                    "source": "igdb",
                    "source_game_id": game_id,
                    "metric_name": "updated_at_epoch",
                    "metric_value": payload.get("updated_at"),
                    "metric_unit": "epoch_seconds",
                    "source_specific_json": {},
                    "stg_loaded_at": now,
                }
            )
        bundle.source_game_urls.extend(_extract_url_rows(payload.get("websites"), game_id, now))
    return bundle


def load_igdb_payloads(repository: IngestionRepository) -> list[tuple[dict[str, Any], str]]:
    rows = repository.fetch_raw_rows("raw.igdb_games")
    payloads_by_game_id: dict[str, tuple[dict[str, Any], str]] = {}
    for row in rows:
        response_json = row.get("response_json")
        if not isinstance(response_json, dict):
            continue
        game_id = str(response_json.get("id") or "").strip()
        if not game_id:
            continue
        payloads_by_game_id[game_id] = (response_json, str(row.get("loaded_at")))
    return list(payloads_by_game_id.values())


def write_bundle(repository: IngestionRepository, bundle: IGDBStagingBundle) -> None:
    repository.replace_source_staging_rows(
        source="igdb",
        table_name="stg.source_games",
        rows=bundle.source_games,
        key_columns=["source", "source_game_id"],
    )
    repository.replace_source_staging_rows(
        source="igdb",
        table_name="stg.source_game_aliases",
        rows=bundle.source_game_aliases,
        key_columns=["source", "source_game_id", "alias", "alias_type"],
    )
    repository.replace_source_staging_rows(
        source="igdb",
        table_name="stg.source_game_external_ids",
        rows=bundle.source_game_external_ids,
        key_columns=["source", "source_game_id", "external_source", "external_id"],
    )
    repository.replace_source_staging_rows(
        source="igdb",
        table_name="stg.source_game_genres",
        rows=bundle.source_game_genres,
        key_columns=["source", "source_game_id", "genre_name"],
    )
    repository.replace_source_staging_rows(
        source="igdb",
        table_name="stg.source_game_tags",
        rows=bundle.source_game_tags,
        key_columns=["source", "source_game_id", "tag_name"],
    )
    repository.replace_source_staging_rows(
        source="igdb",
        table_name="stg.source_game_themes",
        rows=bundle.source_game_themes,
        key_columns=["source", "source_game_id", "theme_name"],
    )
    repository.replace_source_staging_rows(
        source="igdb",
        table_name="stg.source_game_platforms",
        rows=bundle.source_game_platforms,
        key_columns=["source", "source_game_id", "platform_name"],
    )
    repository.replace_source_staging_rows(
        source="igdb",
        table_name="stg.source_game_companies",
        rows=bundle.source_game_companies,
        key_columns=["source", "source_game_id", "company_name", "company_role"],
    )
    repository.replace_source_staging_rows(
        source="igdb",
        table_name="stg.source_game_descriptions",
        rows=bundle.source_game_descriptions,
        key_columns=["source", "source_game_id", "description_type"],
    )
    repository.replace_source_staging_rows(
        source="igdb",
        table_name="stg.source_game_ratings",
        rows=bundle.source_game_ratings,
        key_columns=["source", "source_game_id", "rating_type"],
    )
    repository.replace_source_staging_rows(
        source="igdb",
        table_name="stg.source_game_popularity",
        rows=bundle.source_game_popularity,
        key_columns=["source", "source_game_id", "metric_name"],
    )
    repository.replace_source_staging_rows(
        source="igdb",
        table_name="stg.source_game_urls",
        rows=bundle.source_game_urls,
        key_columns=["source", "source_game_id", "url_type", "url"],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Transform IGDB raw payloads into staging rows.")
    parser.add_argument("--dry-run", action="store_true", help="Preview staging actions only.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run:
        print(
            {
                "source": "igdb",
                "raw_table": "raw.igdb_games",
                "target_tables": [
                    "stg.source_games",
                    "stg.source_game_aliases",
                    "stg.source_game_external_ids",
                    "stg.source_game_genres",
                    "stg.source_game_tags",
                    "stg.source_game_themes",
                    "stg.source_game_platforms",
                    "stg.source_game_companies",
                    "stg.source_game_descriptions",
                    "stg.source_game_ratings",
                    "stg.source_game_popularity",
                    "stg.source_game_urls",
                ],
            }
        )
        return 0

    repository = IngestionRepository()
    payloads = load_igdb_payloads(repository)
    if not payloads:
        raise RuntimeError("IGDB raw game details are empty. Run `make igdb-games` first.")
    bundle = transform_igdb_payloads(payloads)
    write_bundle(repository, bundle)
    print({"source_games": len(bundle.source_games), "themes": len(bundle.source_game_themes)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
