"""Populate deterministic non-embedding entity-resolution features."""

from __future__ import annotations

import argparse
from collections import Counter

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
    description_language_match = None
    if source_a.description_languages and source_b.description_languages:
        description_language_match = bool(
            source_a.description_languages & source_b.description_languages
        )
    else:
        reasons["description_language_match"] = "missing description languages"
    source_count_signal = len(source_a.evidence_sources | source_b.evidence_sources) or None

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
        "description_language_match": description_language_match,
        "source_count_signal": source_count_signal,
        "features_json": {
            "reasons": reasons,
            "alias_overlap_count": len(alias_overlap),
            "source_a_has_description": source_a.has_description,
            "source_b_has_description": source_b.has_description,
            "source_a_description_languages": sorted(source_a.description_languages),
            "source_b_description_languages": sorted(source_b.description_languages),
            "source_a_evidence_sources": sorted(source_a.evidence_sources),
            "source_b_evidence_sources": sorted(source_b.evidence_sources),
        },
    }


def summarize_feature_rows(feature_rows: list[dict[str, object]]) -> dict[str, object]:
    missing_reasons = Counter()
    for row in feature_rows:
        reasons = row.get("features_json", {}).get("reasons", {})
        if isinstance(reasons, dict):
            missing_reasons.update(str(key) for key in reasons)

    return {
        "feature_pair_count": len(feature_rows),
        "description_available_count": sum(
            bool(row.get("description_available_flag")) for row in feature_rows
        ),
        "description_language_match_count": sum(
            bool(row.get("description_language_match")) for row in feature_rows
        ),
        "external_id_exact_match_count": sum(
            bool(row.get("external_id_exact_match")) for row in feature_rows
        ),
        "missing_feature_reason_count": dict(sorted(missing_reasons.items())),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build non-embedding entity-resolution features.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview feature-base generation without writing.",
    )
    parser.add_argument("--limit", type=int, help="Optional pair limit.")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete existing feature rows before rebuild.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run:
        print(
            {
                "limit": args.limit,
                "rebuild": args.rebuild,
                "writes_to": "ml.entity_resolution_features",
            }
        )
        return 0

    repository = IngestionRepository()
    ensure_stage_inputs(repository)
    if args.rebuild:
        repository.delete_entity_resolution_features()
    records = load_source_records(repository)
    pairs = repository.fetch_candidate_pairs(limit=args.limit)
    if not pairs:
        raise RuntimeError(
            "No candidate pairs available. Run `make match-external-ids` "
            "and `make candidate-pairs` first."
        )
    feature_rows: list[dict[str, object]] = []
    for pair in pairs:
        key_a = (str(pair["source_a"]), str(pair["source_id_a"]))
        key_b = (str(pair["source_b"]), str(pair["source_id_b"]))
        if key_a not in records or key_b not in records:
            continue
        feature_row = build_feature_row(pair, records[key_a], records[key_b])
        feature_rows.append(feature_row)
        repository.upsert_entity_resolution_features(**feature_row)
    print(summarize_feature_rows(feature_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
