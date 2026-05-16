"""Populate deterministic non-embedding entity-resolution features."""

from __future__ import annotations

import argparse

from src.entity_resolution.corpus import (
    SourceGameRecord,
    jaccard_similarity,
    load_source_records,
    text_similarity,
)
from src.ingestion.repository import IngestionRepository
from src.preprocessing.validate_data_stage_inputs import ensure_stage_inputs


def build_feature_row(
    pair: dict[str, object],
    source_a: SourceGameRecord,
    source_b: SourceGameRecord,
) -> dict[str, object]:
    reasons: dict[str, str] = {}
    name_similarity = text_similarity(source_a.name_normalized, source_b.name_normalized)
    if name_similarity is None:
        reasons["name_similarity"] = "missing normalized title"

    alias_similarity = None
    alias_overlap = source_a.comparison_names & source_b.comparison_names
    if alias_overlap:
        alias_similarity = 1.0
    elif source_a.aliases and source_b.aliases:
        alias_similarity = max(
            (text_similarity(left, right) or 0.0)
            for left in source_a.aliases
            for right in source_b.aliases
        )
    else:
        reasons["alias_similarity"] = "missing aliases"

    release_year_diff = None
    if source_a.release_year is not None and source_b.release_year is not None:
        release_year_diff = abs(source_a.release_year - source_b.release_year)
    else:
        reasons["release_year_diff"] = "missing release year"

    external_id_exact_match = source_b.external_ids.get("rawg") == source_a.source_game_id
    developer_overlap = jaccard_similarity(source_a.developers, source_b.developers)
    if developer_overlap is None:
        reasons["developer_overlap"] = "missing developer data"
    publisher_overlap = jaccard_similarity(source_a.publishers, source_b.publishers)
    if publisher_overlap is None:
        reasons["publisher_overlap"] = "missing publisher data"
    platform_jaccard = jaccard_similarity(source_a.platforms, source_b.platforms)
    if platform_jaccard is None:
        reasons["platform_jaccard"] = "missing platform data"
    genre_jaccard = jaccard_similarity(source_a.genres, source_b.genres)
    if genre_jaccard is None:
        reasons["genre_jaccard"] = "missing genre data"
    tag_jaccard = jaccard_similarity(source_a.tags, source_b.tags)
    if tag_jaccard is None:
        reasons["tag_jaccard"] = "missing tag data"
    description_available_flag = source_a.has_description and source_b.has_description

    return {
        "pair_id": str(pair["pair_id"]),
        "name_similarity": name_similarity,
        "alias_similarity": alias_similarity,
        "release_year_diff": release_year_diff,
        "external_id_exact_match": external_id_exact_match,
        "developer_overlap": developer_overlap,
        "publisher_overlap": publisher_overlap,
        "platform_jaccard": platform_jaccard,
        "genre_jaccard": genre_jaccard,
        "tag_jaccard": tag_jaccard,
        "description_available_flag": description_available_flag,
        "features_json": {
            "reasons": reasons,
            "alias_overlap_count": len(alias_overlap),
            "source_a_has_description": source_a.has_description,
            "source_b_has_description": source_b.has_description,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build non-embedding entity-resolution features.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview feature-base generation without writing.",
    )
    parser.add_argument("--limit", type=int, help="Optional pair limit.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run:
        print(
            {
                "limit": args.limit,
                "writes_to": "ml.entity_resolution_features",
            }
        )
        return 0

    repository = IngestionRepository()
    ensure_stage_inputs(repository)
    records = load_source_records(repository)
    pairs = repository.fetch_candidate_pairs(limit=args.limit)
    if not pairs:
        raise RuntimeError(
            "No candidate pairs available. Run `make match-external-ids` "
            "and `make candidate-pairs` first."
        )
    for pair in pairs:
        key_a = (str(pair["source_a"]), str(pair["source_id_a"]))
        key_b = (str(pair["source_b"]), str(pair["source_id_b"]))
        if key_a not in records or key_b not in records:
            continue
        feature_row = build_feature_row(pair, records[key_a], records[key_b])
        repository.upsert_entity_resolution_features(**feature_row)
    print({"feature_pair_count": len(pairs)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
