"""Build conservative ML-ready candidate pairs from staged source records."""

from __future__ import annotations

import argparse
from collections import Counter

from src.entity_resolution.corpus import (
    SourceGameRecord,
    load_source_records,
    normalize_text,
    text_similarity,
)
from src.ingestion.repository import IngestionRepository
from src.preprocessing.match_external_ids import find_external_id_matches
from src.preprocessing.validate_data_stage_inputs import ensure_stage_inputs

CANDIDATE_SOURCES = (
    "all",
    "external_id_positive",
    "same_normalized_name",
    "same_release_year_and_similar_name",
    "shared_alias",
)


def summarize_candidate_pairs(pairs: list[dict[str, object]]) -> dict[str, object]:
    count_by_source = Counter(str(pair.get("candidate_source") or "unknown") for pair in pairs)
    positive_weak_label_count = sum(
        str(pair.get("label_value") or "") == "1" for pair in pairs
    )
    manual_review_candidate_count = sum(
        pair.get("label_value") is None and (pair.get("confidence") or 0) >= 0.7
        for pair in pairs
    )
    return {
        "candidate_pair_count": len(pairs),
        "candidate_pair_count_by_source": dict(sorted(count_by_source.items())),
        "positive_weak_label_count": positive_weak_label_count,
        "manual_review_candidate_count": manual_review_candidate_count,
    }


def build_indexes(
    records: dict[tuple[str, str], SourceGameRecord],
    target_source: str,
) -> tuple[
    dict[str, list[SourceGameRecord]],
    dict[tuple[int, str], list[SourceGameRecord]],
    dict[str, list[SourceGameRecord]],
]:
    by_name: dict[str, list[SourceGameRecord]] = {}
    by_year_token: dict[tuple[int, str], list[SourceGameRecord]] = {}
    by_alias: dict[str, list[SourceGameRecord]] = {}
    for key, record in records.items():
        if key[0] != target_source:
            continue
        if record.name_normalized:
            by_name.setdefault(record.name_normalized, []).append(record)
        if record.release_year is not None and record.first_name_token:
            by_year_token.setdefault(
                (record.release_year, record.first_name_token),
                [],
            ).append(record)
        for alias in record.comparison_names:
            by_alias.setdefault(alias, []).append(record)
    return by_name, by_year_token, by_alias


def generate_candidate_pairs(
    records: dict[tuple[str, str], SourceGameRecord],
    *,
    candidate_source: str = "all",
    limit: int | None = None,
) -> list[dict[str, object]]:
    matches = []
    seen_pairs: set[tuple[str, str, str, str]] = set()
    wikidata_by_name, wikidata_by_year_token, wikidata_by_alias = build_indexes(records, "wikidata")

    if candidate_source in {"all", "external_id_positive"}:
        for match in find_external_id_matches(records):
            pair_key = (
                str(match["source_a"]),
                str(match["source_id_a"]),
                str(match["source_b"]),
                str(match["source_id_b"]),
            )
            seen_pairs.add(pair_key)
            matches.append(
                {
                    **match,
                    "candidate_source": "external_id_positive",
                }
            )

    rawg_records = [record for key, record in records.items() if key[0] == "rawg"]
    for rawg_record in rawg_records:
        if candidate_source in {"all", "same_normalized_name"} and rawg_record.name_normalized:
            for wikidata_record in wikidata_by_name.get(rawg_record.name_normalized, []):
                pair_key = (
                    "rawg",
                    rawg_record.source_game_id,
                    "wikidata",
                    wikidata_record.source_game_id,
                )
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                matches.append(
                    {
                        "source_a": "rawg",
                        "source_id_a": rawg_record.source_game_id,
                        "source_b": "wikidata",
                        "source_id_b": wikidata_record.source_game_id,
                        "candidate_source": "same_normalized_name",
                        "label_source": None,
                        "label_value": None,
                        "confidence": 0.8,
                    }
                )

        if (
            candidate_source in {"all", "same_release_year_and_similar_name"}
            and rawg_record.release_year is not None
            and rawg_record.first_name_token
        ):
            for wikidata_record in wikidata_by_year_token.get(
                (rawg_record.release_year, rawg_record.first_name_token),
                [],
            ):
                pair_key = (
                    "rawg",
                    rawg_record.source_game_id,
                    "wikidata",
                    wikidata_record.source_game_id,
                )
                if pair_key in seen_pairs:
                    continue
                similarity = text_similarity(
                    rawg_record.name_normalized,
                    wikidata_record.name_normalized,
                )
                if similarity is None or similarity < 0.75:
                    continue
                seen_pairs.add(pair_key)
                matches.append(
                    {
                        "source_a": "rawg",
                        "source_id_a": rawg_record.source_game_id,
                        "source_b": "wikidata",
                        "source_id_b": wikidata_record.source_game_id,
                        "candidate_source": "same_release_year_and_similar_name",
                        "label_source": None,
                        "label_value": None,
                        "confidence": similarity,
                    }
                )

        if candidate_source in {"all", "shared_alias"}:
            for alias in rawg_record.comparison_names:
                for wikidata_record in wikidata_by_alias.get(alias, []):
                    pair_key = (
                        "rawg",
                        rawg_record.source_game_id,
                        "wikidata",
                        wikidata_record.source_game_id,
                    )
                    if pair_key in seen_pairs or normalize_text(alias) is None:
                        continue
                    seen_pairs.add(pair_key)
                    matches.append(
                        {
                            "source_a": "rawg",
                            "source_id_a": rawg_record.source_game_id,
                            "source_b": "wikidata",
                            "source_id_b": wikidata_record.source_game_id,
                            "candidate_source": "shared_alias",
                            "label_source": None,
                            "label_value": None,
                            "confidence": 0.7,
                        }
                    )

        if limit is not None and len(matches) >= limit:
            break

    if limit is not None:
        return matches[:limit]
    return matches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build conservative entity candidate pairs.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview candidate generation without writing.",
    )
    parser.add_argument("--limit", type=int, help="Optional candidate limit.")
    parser.add_argument(
        "--candidate-source",
        choices=CANDIDATE_SOURCES,
        default="all",
        help="Restrict generation to a single candidate source.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete existing candidate pairs before rebuild.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run:
        print(
            {
                "candidate_source": args.candidate_source,
                "limit": args.limit,
                "rebuild": args.rebuild,
                "writes_to": "ml.entity_candidate_pairs",
            }
        )
        return 0

    repository = IngestionRepository()
    ensure_stage_inputs(repository)
    if args.rebuild:
        repository.delete_candidate_pairs()
    records = load_source_records(repository)
    pairs = generate_candidate_pairs(
        records,
        candidate_source=args.candidate_source,
        limit=args.limit,
    )
    inserted = 0
    for pair in pairs:
        repository.upsert_candidate_pair(**pair)
        inserted += 1
    summary = summarize_candidate_pairs(pairs)
    summary["candidate_source"] = args.candidate_source
    summary["inserted_pair_count"] = inserted
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
