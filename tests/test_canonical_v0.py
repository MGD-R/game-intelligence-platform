from __future__ import annotations

from src.entity_resolution.build_canonical_v0 import (
    build_components,
    build_union_find,
    choose_canonical_record,
    stable_canonical_id,
)
from src.entity_resolution.corpus import SourceGameRecord


def build_records() -> dict[tuple[str, str], SourceGameRecord]:
    rawg = SourceGameRecord(
        source="rawg",
        source_game_id="3498",
        name="Grand Theft Auto V",
        name_normalized="grand theft auto v",
        release_year=2013,
    )
    wikidata = SourceGameRecord(
        source="wikidata",
        source_game_id="Q17452",
        name="Q17452",
        name_normalized="q17452",
        release_year=2013,
        external_ids={"rawg": "3498", "steam": "271590"},
    )
    steam = SourceGameRecord(
        source="steam",
        source_game_id="271590",
        name="Grand Theft Auto V Legacy",
        name_normalized="grand theft auto v legacy",
        release_year=2015,
    )
    igdb = SourceGameRecord(
        source="igdb",
        source_game_id="1020",
        name="Grand Theft Auto V",
        name_normalized="grand theft auto v",
        release_year=2013,
    )
    return {
        ("rawg", "3498"): rawg,
        ("wikidata", "Q17452"): wikidata,
        ("steam", "271590"): steam,
        ("igdb", "1020"): igdb,
    }


def test_build_union_find_links_only_trusted_external_pairs_and_steam() -> None:
    records = build_records()
    pairs = [
        {
            "source_a": "rawg",
            "source_id_a": "3498",
            "source_b": "wikidata",
            "source_id_b": "Q17452",
            "candidate_source": "external_id",
            "label_value": "1",
        },
        {
            "source_a": "rawg",
            "source_id_a": "3498",
            "source_b": "igdb",
            "source_id_b": "1020",
            "candidate_source": "igdb_search",
            "label_value": None,
        },
    ]

    union_find = build_union_find(records, pairs)

    assert union_find.find(("rawg", "3498")) == union_find.find(("wikidata", "Q17452"))
    assert union_find.find(("rawg", "3498")) == union_find.find(("steam", "271590"))
    assert union_find.find(("rawg", "3498")) != union_find.find(("igdb", "1020"))


def test_build_union_find_links_canonical_v1_edges() -> None:
    records = build_records()
    pairs = [
        {
            "source_a": "rawg",
            "source_id_a": "3498",
            "source_b": "igdb",
            "source_id_b": "1020",
            "candidate_source": "igdb_search",
            "label_value": "1",
            "canonical_edge": True,
        }
    ]

    union_find = build_union_find(records, pairs)

    assert union_find.find(("rawg", "3498")) == union_find.find(("igdb", "1020"))


def test_choose_canonical_record_prefers_rawg_over_wikidata_qid_name() -> None:
    records = build_records()

    record = choose_canonical_record(records, {("rawg", "3498"), ("wikidata", "Q17452")})

    assert record.source == "rawg"
    assert record.name == "Grand Theft Auto V"


def test_build_components_uses_stable_ids() -> None:
    records = build_records()
    pairs = [
        {
            "source_a": "rawg",
            "source_id_a": "3498",
            "source_b": "wikidata",
            "source_id_b": "Q17452",
            "candidate_source": "external_id",
            "label_value": "1",
        }
    ]

    components = build_components(records, pairs)
    merged = [
        component
        for component in components
        if ("rawg", "3498") in component.source_keys
        and ("wikidata", "Q17452") in component.source_keys
    ][0]

    assert merged.canonical_game_id == stable_canonical_id(set(merged.source_keys))
    assert merged.canonical_name == "Grand Theft Auto V"
    assert merged.release_year == 2013
