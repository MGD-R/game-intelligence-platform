from __future__ import annotations

from src.entity_resolution.build_candidate_pairs import (
    generate_candidate_pairs,
    summarize_candidate_pairs,
)
from src.entity_resolution.corpus import SourceGameRecord


def build_records() -> dict[tuple[str, str], SourceGameRecord]:
    rawg = SourceGameRecord(
        source="rawg",
        source_game_id="3498",
        name="Grand Theft Auto V",
        name_normalized="grand theft auto v",
        release_year=2013,
        aliases={"gta v"},
    )
    wikidata_match = SourceGameRecord(
        source="wikidata",
        source_game_id="Q12345",
        name="Grand Theft Auto V",
        name_normalized="grand theft auto v",
        release_year=2013,
        aliases={"gta v", "game example"},
        external_ids={"rawg": "3498"},
    )
    wikidata_other = SourceGameRecord(
        source="wikidata",
        source_game_id="Q99999",
        name="Unrelated Puzzle",
        name_normalized="unrelated puzzle",
        release_year=2011,
        aliases={"puzzle"},
    )
    return {
        ("rawg", "3498"): rawg,
        ("wikidata", "Q12345"): wikidata_match,
        ("wikidata", "Q99999"): wikidata_other,
    }


def test_same_normalized_name_creates_candidate_pair() -> None:
    pairs = generate_candidate_pairs(build_records(), candidate_source="same_normalized_name")

    assert len(pairs) == 1
    assert pairs[0]["source_id_b"] == "Q12345"
    assert pairs[0]["candidate_source"] == "same_normalized_name"


def test_unrelated_names_do_not_create_candidate_pair() -> None:
    pairs = generate_candidate_pairs(build_records(), candidate_source="shared_alias")

    assert len(pairs) == 1
    assert all(pair["source_id_b"] != "Q99999" for pair in pairs)


def test_candidate_summary_counts_manual_review_rows() -> None:
    summary = summarize_candidate_pairs(generate_candidate_pairs(build_records()))

    assert summary["candidate_pair_count"] >= 1
    assert summary["positive_weak_label_count"] == 1
