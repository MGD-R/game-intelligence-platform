"""Select search-based IGDB candidate seeds from the staged corpus."""

from __future__ import annotations

import json
import os
from pathlib import Path

from src.ingestion.cli import build_common_parser
from src.ingestion.igdb_auth import load_igdb_settings
from src.ingestion.repository import IngestionRepository
from src.preprocessing.normalize_text import normalize_title_text


def default_limit() -> int:
    settings = load_igdb_settings()
    return int(os.getenv("IGDB_SEARCH_LIMIT", settings.get("demo_limit", 50)))


def _slug_to_title(slug: str | None) -> str | None:
    if not slug:
        return None
    title = " ".join(part for part in str(slug).replace("_", "-").split("-") if part)
    return title.strip() or None


def build_linked_wikidata_aliases(
    *,
    rawg_rows: list[dict[str, object]],
    external_rows: list[dict[str, object]],
    alias_rows: list[dict[str, object]],
) -> dict[str, list[str]]:
    rawg_slug_by_id = {
        str(row["source_game_id"]): str(row.get("slug") or "").strip()
        for row in rawg_rows
        if row.get("slug")
    }
    qids_by_slug: dict[str, set[str]] = {}
    for row in external_rows:
        if row.get("source") != "wikidata" or row.get("external_source") != "rawg":
            continue
        slug = str(row.get("external_id") or "").strip()
        qid = str(row.get("source_game_id") or "").strip()
        if slug and qid:
            qids_by_slug.setdefault(slug, set()).add(qid)

    aliases_by_qid: dict[str, list[str]] = {}
    seen_by_qid: dict[str, set[str]] = {}
    for row in alias_rows:
        if row.get("source") != "wikidata":
            continue
        qid = str(row.get("source_game_id") or "").strip()
        alias = str(row.get("alias") or "").strip()
        if not qid or not alias:
            continue
        normalized = normalize_title_text(alias)
        if not normalized:
            continue
        seen = seen_by_qid.setdefault(qid, set())
        if normalized in seen:
            continue
        seen.add(normalized)
        aliases_by_qid.setdefault(qid, []).append(alias)

    aliases_by_rawg_id: dict[str, list[str]] = {}
    for rawg_id, slug in rawg_slug_by_id.items():
        qids = qids_by_slug.get(slug, set())
        aliases: list[str] = []
        seen: set[str] = set()
        for qid in sorted(qids):
            for alias in aliases_by_qid.get(qid, []):
                normalized = normalize_title_text(alias)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                aliases.append(alias)
        if aliases:
            aliases_by_rawg_id[rawg_id] = aliases
    return aliases_by_rawg_id


def build_search_queries(
    *,
    name: str,
    slug: str | None,
    aliases: list[str],
    alias_limit: int,
) -> list[dict[str, str]]:
    queries: list[dict[str, str]] = []
    seen: set[str] = set()

    def add_query(query_text: str | None, strategy: str) -> None:
        if not query_text:
            return
        cleaned = str(query_text).strip()
        normalized = normalize_title_text(cleaned)
        if not cleaned or not normalized or normalized in seen:
            return
        seen.add(normalized)
        queries.append({"query_text": cleaned, "query_strategy": strategy})

    add_query(name, "source_name")
    add_query(_slug_to_title(slug), "rawg_slug")
    for alias in aliases[: max(0, alias_limit)]:
        add_query(alias, "wikidata_alias")
    return queries


def extract_attempted_source_ids(raw_search_rows: list[dict[str, object]]) -> set[str]:
    attempted: set[str] = set()
    for row in raw_search_rows:
        payload = row.get("response_json")
        if not isinstance(payload, dict):
            continue
        anchor = payload.get("anchor")
        if not isinstance(anchor, dict):
            continue
        source_name = str(anchor.get("source") or "").strip()
        source_game_id = str(anchor.get("source_game_id") or "").strip()
        if source_name == "rawg" and source_game_id:
            attempted.add(source_game_id)
    return attempted


def select_igdb_search_seeds_from_rows(
    *,
    rawg_rows: list[dict[str, object]],
    external_rows: list[dict[str, object]],
    alias_rows: list[dict[str, object]],
    existing_candidate_rows: list[dict[str, object]] | None = None,
    limit: int | None = None,
    alias_limit: int = 2,
    unmatched_only: bool = False,
    missing_only: bool = False,
) -> list[dict[str, object]]:
    rawg_slug_by_id = {
        str(row["source_game_id"]): str(row.get("slug") or "").strip()
        for row in rawg_rows
        if row.get("slug")
    }
    linked_rawg_ids = {
        rawg_id
        for rawg_id, slug in rawg_slug_by_id.items()
        if any(
            row.get("source") == "wikidata"
            and row.get("external_source") == "rawg"
            and str(row.get("external_id") or "").strip() == slug
            for row in external_rows
        )
    }
    aliases_by_rawg_id = build_linked_wikidata_aliases(
        rawg_rows=rawg_rows,
        external_rows=external_rows,
        alias_rows=alias_rows,
    )
    existing_ids = {
        str(row.get("source_game_id") or "")
        for row in (existing_candidate_rows or [])
        if str(row.get("source_name") or "") == "rawg"
    }
    seeds: list[dict[str, object]] = []
    sorted_rows = sorted(
        rawg_rows,
        key=lambda row: (
            -int(row.get("source_priority") or 0),
            str(row.get("release_date") or ""),
            str(row.get("source_game_id") or ""),
        ),
    )
    for row in sorted_rows:
        rawg_id = str(row.get("source_game_id") or "").strip()
        name = str(row.get("name") or "").strip()
        slug = str(row.get("slug") or "").strip() or None
        if not rawg_id or not name:
            continue
        matched_to_wikidata = rawg_id in linked_rawg_ids
        if unmatched_only and matched_to_wikidata:
            continue
        if missing_only and rawg_id in existing_ids:
            continue
        queries = build_search_queries(
            name=name,
            slug=slug,
            aliases=aliases_by_rawg_id.get(rawg_id, []),
            alias_limit=alias_limit,
        )
        if not queries:
            continue
        seeds.append(
            {
                "source": "rawg",
                "source_game_id": rawg_id,
                "name": name,
                "slug": slug,
                "release_year": row.get("release_year"),
                "matched_to_wikidata": matched_to_wikidata,
                "queries": queries,
            }
        )
        if limit is not None and len(seeds) >= limit:
            break
    return seeds


def main(argv: list[str] | None = None) -> int:
    parser = build_common_parser("Select search-based IGDB seeds from RAWG staging rows.")
    parser.add_argument("--output-file", help="Optional JSON file with selected seeds.")
    parser.add_argument("--alias-limit", type=int, default=2)
    parser.add_argument("--unmatched-only", action="store_true")
    parser.add_argument("--missing-only", action="store_true")
    parser.set_defaults(limit=default_limit())
    args = parser.parse_args(argv)

    if args.dry_run:
        print(
            {
                "selection_source": "stg.source_games",
                "filters": {
                    "source": "rawg",
                    "unmatched_only": args.unmatched_only,
                    "missing_only": args.missing_only,
                },
                "alias_limit": args.alias_limit,
                "limit": args.limit,
                "output_file": args.output_file,
            }
        )
        return 0

    repository = IngestionRepository()
    rawg_rows = repository.fetch_staging_rows("stg.source_games", source="rawg")
    if not rawg_rows:
        raise RuntimeError("RAWG staging is empty. Run `make rawg-staging` first.")
    external_rows = repository.fetch_staging_rows(
        "stg.source_game_external_ids", source="wikidata"
    )
    alias_rows = repository.fetch_staging_rows("stg.source_game_aliases", source="wikidata")
    existing_rows = (
        repository.fetch_igdb_search_candidates(source_name="rawg")
        if args.missing_only
        else []
    )
    attempted_ids: set[str] = set()
    if args.missing_only:
        repository.ensure_igdb_search_results_table()
        attempted_rows = repository.fetch_staging_rows("raw.igdb_search_results")
        attempted_ids = extract_attempted_source_ids(attempted_rows)
    seeds = select_igdb_search_seeds_from_rows(
        rawg_rows=rawg_rows,
        external_rows=external_rows,
        alias_rows=alias_rows,
        existing_candidate_rows=existing_rows,
        limit=args.limit,
        alias_limit=args.alias_limit,
        unmatched_only=args.unmatched_only,
        missing_only=args.missing_only,
    )
    if attempted_ids:
        seeds = [
            seed
            for seed in seeds
            if str(seed.get("source_game_id") or "").strip() not in attempted_ids
        ]
        if args.limit is not None:
            seeds = seeds[: args.limit]
    if not seeds:
        raise RuntimeError(
            "No IGDB search seeds available. "
            "Run `make rawg-staging` and `make wikidata-staging` first."
        )
    if args.output_file:
        Path(args.output_file).write_text(json.dumps(seeds, indent=2) + "\n", encoding="utf-8")
    print({"selected_count": len(seeds), "output_file": args.output_file, "sample": seeds[:3]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
