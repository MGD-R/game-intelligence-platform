from __future__ import annotations

from src.entity_resolution.corpus import SourceGameRecord
from src.preprocessing.match_external_ids import find_external_id_matches


def build_records() -> dict[tuple[str, str], SourceGameRecord]:
    return {
        ("rawg", "3498"): SourceGameRecord(
            source="rawg",
            source_game_id="3498",
            name="Grand Theft Auto V",
            name_normalized="grand theft auto v",
            release_year=2013,
        ),
        ("wikidata", "Q12345"): SourceGameRecord(
            source="wikidata",
            source_game_id="Q12345",
            name="Grand Theft Auto V",
            name_normalized="grand theft auto v",
            release_year=2013,
            external_ids={"rawg": "3498"},
        ),
    }


def test_rawg_matches_wikidata_rawg_external_id() -> None:
    matches = find_external_id_matches(build_records())

    assert matches == [
        {
            "source_a": "rawg",
            "source_id_a": "3498",
            "source_b": "wikidata",
            "source_id_b": "Q12345",
            "candidate_source": "external_id",
            "label_source": "wikidata_rawg_external_id",
            "label_value": "1",
            "confidence": 1.0,
        }
    ]


def test_external_id_matching_is_deterministic() -> None:
    first = find_external_id_matches(build_records())
    second = find_external_id_matches(build_records())

    assert first == second
