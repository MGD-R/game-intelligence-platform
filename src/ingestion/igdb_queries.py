"""IGDB APICalypse query builders."""

from __future__ import annotations

from datetime import UTC, datetime

FIELDS_GAMES = [
    "id",
    "name",
    "slug",
    "alternative_names.name",
    "first_release_date",
    "release_dates.date",
    "release_dates.platform.name",
    "release_dates.region",
    "genres.name",
    "themes.name",
    "keywords.name",
    "platforms.name",
    "involved_companies.company.name",
    "involved_companies.developer",
    "involved_companies.publisher",
    "involved_companies.porting",
    "involved_companies.supporting",
    "game_localizations.name",
    "language_supports.language.name",
    "language_supports.language_support_type.name",
    "summary",
    "storyline",
    "rating",
    "rating_count",
    "aggregated_rating",
    "aggregated_rating_count",
    "total_rating",
    "total_rating_count",
    "external_games.*",
    "websites.*",
    "collections.name",
    "franchises.name",
    "similar_games.name",
    "version_parent",
    "version_title",
    "game_type",
    "updated_at",
]

REFERENCE_ENDPOINTS = (
    "genres",
    "themes",
    "keywords",
    "platforms",
    "platform_families",
    "platform_types",
    "companies",
    "external_game_sources",
    "game_modes",
    "player_perspectives",
)


def _escape_search_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').strip()


def _fields_clause(fields: list[str]) -> str:
    return "fields " + ", ".join(fields) + ";"


def build_games_by_ids_query(ids: list[int], fields: list[str] | None = None) -> str:
    if not ids:
        raise ValueError("At least one IGDB ID is required.")
    resolved_fields = fields or FIELDS_GAMES
    joined_ids = ", ".join(str(game_id) for game_id in ids)
    return f"{_fields_clause(resolved_fields)} where id = ({joined_ids}); limit {len(ids)};"


def build_reference_query(endpoint: str) -> str:
    return "fields id, name, slug, updated_at; sort id asc; limit 500;"


def build_search_games_query(
    query_text: str,
    *,
    fields: list[str] | None = None,
    limit: int = 5,
    release_year: int | None = None,
    year_window: int = 0,
) -> str:
    cleaned_query = _escape_search_text(query_text)
    if not cleaned_query:
        raise ValueError("Search query text is required.")
    resolved_fields = fields or FIELDS_GAMES
    limit_clause = max(1, limit)
    parts = [_fields_clause(resolved_fields), f'search "{cleaned_query}";']
    if release_year is not None:
        lower_year = release_year - max(0, year_window)
        upper_year = release_year + max(0, year_window) + 1
        lower_epoch = int(datetime(lower_year, 1, 1, tzinfo=UTC).timestamp())
        upper_epoch = int(datetime(upper_year, 1, 1, tzinfo=UTC).timestamp())
        parts.append(
            "where first_release_date != null"
            f" & first_release_date >= {lower_epoch}"
            f" & first_release_date < {upper_epoch};"
        )
    parts.append(f"limit {limit_clause};")
    return " ".join(parts)


def build_external_games_query(ids: list[int]) -> str:
    if not ids:
        raise ValueError("At least one IGDB ID is required.")
    joined_ids = ", ".join(str(game_id) for game_id in ids)
    return (
        "fields id, game, category, uid, external_game_source.name, url; "
        f"where game = ({joined_ids}); limit 500;"
    )


def build_multiquery_reference() -> list[tuple[str, str]]:
    return [
        (endpoint, f'query {endpoint} "{endpoint}" {{ {build_reference_query(endpoint)} }};')
        for endpoint in REFERENCE_ENDPOINTS
    ]
