"""Normalize IGDB search raw rows into auditable ML candidate rows."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from src.ingestion.repository import IngestionRepository
from src.preprocessing.igdb_to_staging import parse_unix_date


@dataclass(slots=True)
class IGDBSearchCandidateRow:
    source_name: str
    source_game_id: str
    candidate_source: str
    igdb_id: str
    search_rank: int
    query_text: str
    query_strategy: str
    confidence: float | None
    metadata_json: dict[str, object]


def _release_year_from_candidate(candidate: dict[str, Any]) -> int | None:
    _, release_year = parse_unix_date(candidate.get("first_release_date"))
    return release_year


def _calculate_confidence(
    *,
    search_rank: int,
    query_strategy: str,
    anchor_release_year: int | None,
    candidate_release_year: int | None,
) -> float:
    rank_penalty = min(max(search_rank - 1, 0) * 0.1, 0.4)
    strategy_bonus = 0.1 if query_strategy == "wikidata_alias" else 0.0
    year_bonus = 0.0
    if anchor_release_year is not None and candidate_release_year is not None:
        if anchor_release_year == candidate_release_year:
            year_bonus = 0.1
        elif abs(anchor_release_year - candidate_release_year) <= 1:
            year_bonus = 0.05
    confidence = 0.85 - rank_penalty + strategy_bonus + year_bonus
    return round(max(0.1, min(confidence, 0.99)), 4)


def extract_candidate_rows(raw_rows: list[dict[str, Any]]) -> list[IGDBSearchCandidateRow]:
    rows_by_key: dict[tuple[str, str, str], IGDBSearchCandidateRow] = {}
    for row in raw_rows:
        payload = row.get("response_json")
        if not isinstance(payload, dict):
            continue
        anchor = payload.get("anchor")
        query = payload.get("query")
        candidate = payload.get("candidate")
        if (
            not isinstance(anchor, dict)
            or not isinstance(query, dict)
            or not isinstance(candidate, dict)
        ):
            continue
        source_name = str(anchor.get("source") or "").strip()
        source_game_id = str(anchor.get("source_game_id") or "").strip()
        igdb_id = str(candidate.get("id") or "").strip()
        query_text = str(query.get("text") or "").strip()
        query_strategy = str(query.get("strategy") or "").strip()
        search_rank = int(query.get("rank") or 0)
        if (
            not source_name
            or not source_game_id
            or not igdb_id
            or not query_text
            or not query_strategy
        ):
            continue
        if search_rank <= 0:
            continue
        anchor_release_year = (
            int(anchor["release_year"]) if anchor.get("release_year") is not None else None
        )
        candidate_release_year = _release_year_from_candidate(candidate)
        candidate_row = IGDBSearchCandidateRow(
            source_name=source_name,
            source_game_id=source_game_id,
            candidate_source="igdb",
            igdb_id=igdb_id,
            search_rank=search_rank,
            query_text=query_text,
            query_strategy=query_strategy,
            confidence=_calculate_confidence(
                search_rank=search_rank,
                query_strategy=query_strategy,
                anchor_release_year=anchor_release_year,
                candidate_release_year=candidate_release_year,
            ),
            metadata_json={
                "anchor_name": anchor.get("name"),
                "anchor_slug": anchor.get("slug"),
                "anchor_release_year": anchor.get("release_year"),
                "matched_to_wikidata": bool(anchor.get("matched_to_wikidata")),
                "candidate_name": candidate.get("name"),
                "candidate_release_year": candidate_release_year,
                "candidate_slug": candidate.get("slug"),
                "retrieved_from_request_hash": row.get("request_hash"),
            },
        )
        key = (source_name, source_game_id, igdb_id)
        current = rows_by_key.get(key)
        if current is None or candidate_row.search_rank < current.search_rank:
            rows_by_key[key] = candidate_row
    return list(rows_by_key.values())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build IGDB search candidates from raw search rows."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source-name", default="rawg")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--promote-pairs", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run:
        print(
            {
                "source_name": args.source_name,
                "limit": args.limit,
                "rebuild": args.rebuild,
                "promote_pairs": args.promote_pairs,
                "writes_to": ["ml.igdb_search_candidates", "ml.entity_candidate_pairs"],
            }
        )
        return 0

    repository = IngestionRepository()
    repository.ensure_igdb_search_results_table()
    repository.ensure_igdb_search_candidates_table()
    if args.rebuild:
        repository.delete_igdb_search_candidates(source_name=args.source_name)
    raw_rows = repository.fetch_raw_rows("raw.igdb_search_results")
    candidate_rows = [
        row
        for row in extract_candidate_rows(raw_rows)
        if row.source_name == args.source_name
    ]
    if args.limit is not None:
        candidate_rows = candidate_rows[: args.limit]
    if not candidate_rows:
        raise RuntimeError("IGDB search raw rows are empty. Run `make igdb-search` first.")

    promoted_pairs = 0
    for row in candidate_rows:
        repository.upsert_igdb_search_candidate(
            source_name=row.source_name,
            source_game_id=row.source_game_id,
            candidate_source=row.candidate_source,
            igdb_id=row.igdb_id,
            search_rank=row.search_rank,
            query_text=row.query_text,
            query_strategy=row.query_strategy,
            confidence=row.confidence,
            metadata_json=row.metadata_json,
        )
        if args.promote_pairs:
            repository.upsert_candidate_pair(
                source_a=row.source_name,
                source_id_a=row.source_game_id,
                source_b="igdb",
                source_id_b=row.igdb_id,
                candidate_source="igdb_search",
                label_source=None,
                label_value=None,
                confidence=row.confidence,
            )
            promoted_pairs += 1
    print(
        {
            "candidate_rows": len(candidate_rows),
            "promoted_pairs": promoted_pairs,
            "source_name": args.source_name,
            "built_at": datetime.now(UTC).isoformat(),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
