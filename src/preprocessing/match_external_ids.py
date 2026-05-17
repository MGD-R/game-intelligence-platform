"""Deterministic RAWG-to-Wikidata matching by external IDs."""

from __future__ import annotations

import argparse

from src.entity_resolution.corpus import SourceGameRecord, load_source_records
from src.ingestion.repository import IngestionRepository
from src.preprocessing.validate_data_stage_inputs import ensure_stage_inputs


def find_external_id_matches(
    records: dict[tuple[str, str], SourceGameRecord],
    *,
    source_a: str = "rawg",
    source_b: str = "wikidata",
) -> list[dict[str, object]]:
    rawg_records = {key[1]: record for key, record in records.items() if key[0] == source_a}
    wikidata_records = [record for key, record in records.items() if key[0] == source_b]
    matches: list[dict[str, object]] = []
    for wikidata_record in wikidata_records:
        rawg_id = wikidata_record.external_ids.get("rawg")
        if not rawg_id or rawg_id not in rawg_records:
            continue
        matches.append(
            {
                "source_a": source_a,
                "source_id_a": rawg_id,
                "source_b": source_b,
                "source_id_b": wikidata_record.source_game_id,
                "candidate_source": "external_id",
                "label_source": "wikidata_rawg_external_id",
                "label_value": "1",
                "confidence": 1.0,
            }
        )
    return sorted(matches, key=lambda item: (str(item["source_id_a"]), str(item["source_id_b"])))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Match source records by deterministic external IDs."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview deterministic matches without writing.",
    )
    parser.add_argument("--source-a", default="rawg", help="Left source name.")
    parser.add_argument("--source-b", default="wikidata", help="Right source name.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run:
        preview = {
            "source_a": args.source_a,
            "source_b": args.source_b,
            "rule": "RAWG source_game_id == Wikidata external_id where external_source='rawg'",
            "writes_to": "ml.entity_candidate_pairs",
        }
        print(preview)
        return 0

    repository = IngestionRepository()
    ensure_stage_inputs(repository)
    records = load_source_records(repository)
    matches = find_external_id_matches(records, source_a=args.source_a, source_b=args.source_b)
    for match in matches:
        repository.upsert_candidate_pair(**match)
    print(
        {
            "source_a": args.source_a,
            "source_b": args.source_b,
            "deterministic_match_count": len(matches),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
