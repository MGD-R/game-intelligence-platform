from __future__ import annotations

from src.entity_resolution.build_feature_base import build_feature_row
from src.entity_resolution.corpus import SourceGameRecord


def test_basic_name_similarity_and_release_year_diff() -> None:
    rawg = SourceGameRecord(
        source="rawg",
        source_game_id="3498",
        name="Grand Theft Auto V",
        name_normalized="grand theft auto v",
        release_year=2013,
        aliases={"gta v"},
        external_ids={},
        genres={"action", "adventure"},
        platforms={"pc", "playstation 5"},
        developers={"rockstar north"},
        publishers={"rockstar games"},
        has_description=True,
    )
    wikidata = SourceGameRecord(
        source="wikidata",
        source_game_id="Q12345",
        name="Grand Theft Auto V",
        name_normalized="grand theft auto v",
        release_year=2013,
        aliases={"gta v"},
        external_ids={"rawg": "3498"},
        genres={"action", "adventure"},
        platforms={"pc"},
        developers={"rockstar north"},
        publishers={"rockstar games"},
        has_description=True,
    )
    row = build_feature_row({"pair_id": "pair-1"}, rawg, wikidata)

    assert row["name_similarity"] == 1.0
    assert row["alias_similarity"] == 1.0
    assert row["release_year_diff"] == 0
    assert row["external_id_exact_match"] is True
    assert row["platform_jaccard"] == 0.5


def test_missing_values_are_reported_in_features_json() -> None:
    rawg = SourceGameRecord(
        source="rawg",
        source_game_id="1",
        name="Foo",
        name_normalized="foo",
        release_year=None,
    )
    wikidata = SourceGameRecord(
        source="wikidata",
        source_game_id="Q1",
        name="Bar",
        name_normalized="bar",
        release_year=None,
    )
    row = build_feature_row({"pair_id": "pair-2"}, rawg, wikidata)

    assert row["release_year_diff"] is None
    assert "release_year_diff" in row["features_json"]["reasons"]
