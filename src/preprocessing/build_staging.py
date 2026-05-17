"""Staging rebuild orchestration for RAWG and Wikidata."""

from __future__ import annotations

import argparse

from src.ingestion.repository import IngestionRepository
from src.preprocessing.normalize_dates import normalize_release_date
from src.preprocessing.normalize_flags import infer_flag_set
from src.preprocessing.normalize_text import normalize_title_text
from src.preprocessing.rawg_to_staging import (
    load_rawg_payloads,
    transform_rawg_payloads,
)
from src.preprocessing.rawg_to_staging import (
    write_bundle as write_rawg_bundle,
)
from src.preprocessing.wikidata_to_staging import (
    load_wikidata_payloads,
    transform_wikidata_payloads,
)
from src.preprocessing.wikidata_to_staging import (
    write_bundle as write_wikidata_bundle,
)


def refresh_source_games(
    repository: IngestionRepository,
    *,
    source: str,
    source_priority: int,
    limit: int | None = None,
) -> int:
    rows = repository.fetch_staging_rows("stg.source_games", source=source)
    if limit is not None:
        rows = rows[:limit]
    normalized_rows: list[dict[str, object]] = []
    for row in rows:
        normalized_name = normalize_title_text(str(row["name"])) if row.get("name") else None
        release_date, release_year, quality_reason = normalize_release_date(
            str(row["release_date"]) if row.get("release_date") else None
        )
        flags, flag_reasons = infer_flag_set({"name": row.get("name")})
        quality_flags = dict(row.get("quality_flags_json") or {})
        if normalized_name and normalized_name != row.get("name_normalized"):
            quality_flags["normalized_name_refreshed"] = True
        if quality_reason:
            quality_flags[quality_reason] = True
        for reason in flag_reasons:
            quality_flags[reason] = True
        normalized_rows.append(
            {
                **row,
                "name_normalized": normalized_name,
                "release_date": release_date,
                "release_year": release_year,
                "source_priority": source_priority,
                "quality_flags_json": quality_flags,
                **flags,
            }
        )
    repository.replace_source_staging_rows(
        source=source,
        table_name="stg.source_games",
        rows=normalized_rows,
        key_columns=["source", "source_game_id"],
    )
    return len(normalized_rows)


def run_source_staging(
    repository: IngestionRepository,
    *,
    source: str,
    limit: int | None = None,
) -> dict[str, object]:
    if source == "rawg":
        if (
            repository.count_rows("raw.rawg_game_index") == 0
            and repository.count_rows("raw.rawg_game_details") == 0
        ):
            raise RuntimeError("RAWG raw tables are empty. Run `make rawg-demo` first.")
        index_payloads, details_payloads = load_rawg_payloads(repository)
        if limit is not None:
            index_payloads = index_payloads[:limit]
            details_payloads = dict(list(details_payloads.items())[:limit])
        bundle = transform_rawg_payloads(index_payloads, details_payloads)
        write_rawg_bundle(repository, bundle)
        normalized = refresh_source_games(
            repository,
            source="rawg",
            source_priority=100,
            limit=limit,
        )
        return {"source": "rawg", "normalized_rows": normalized}

    if source == "wikidata":
        if (
            repository.count_rows("raw.wikidata_sparql_results") == 0
            and repository.count_rows("raw.wikidata_entities") == 0
        ):
            raise RuntimeError(
                "Wikidata raw tables are empty. Run `make wikidata-by-rawg` first."
            )
        sparql_payloads, entity_payloads = load_wikidata_payloads(repository)
        if limit is not None:
            sparql_payloads = sparql_payloads[:limit]
            entity_payloads = dict(list(entity_payloads.items())[:limit])
        bundle = transform_wikidata_payloads(sparql_payloads, entity_payloads)
        write_wikidata_bundle(repository, bundle)
        normalized = refresh_source_games(
            repository,
            source="wikidata",
            source_priority=80,
            limit=limit,
        )
        return {"source": "wikidata", "normalized_rows": normalized}

    raise ValueError(f"Unsupported source for staging build: {source}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and normalize staging tables.")
    parser.add_argument("--source", choices=("rawg", "wikidata"), help="Single source to rebuild.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Rebuild all currently supported sources.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview staging actions without writing.",
    )
    parser.add_argument("--rebuild", action="store_true", help="Accept explicit rebuild intent.")
    parser.add_argument("--limit", type=int, help="Optional row/payload limit for debug rebuilds.")
    args = parser.parse_args()

    sources = [args.source] if args.source else []
    if args.all:
        sources = ["rawg", "wikidata"]
    if not sources:
        sources = ["rawg", "wikidata"]

    if args.dry_run:
        print({"sources": sources, "rebuild": args.rebuild, "limit": args.limit})
        return 0

    repository = IngestionRepository()
    summary = [
        run_source_staging(repository, source=source, limit=args.limit) for source in sources
    ]
    print({"rebuilt_sources": summary})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
