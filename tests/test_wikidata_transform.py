from __future__ import annotations

import json
from pathlib import Path

from src.preprocessing.wikidata_to_staging import transform_wikidata_payloads

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "wikidata"


def read_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_transform_wikidata_payloads_builds_expected_rows() -> None:
    sparql_payloads = [
        (read_fixture("identity_external_ids.json"), "2026-05-16T10:00:00+00:00"),
        (read_fixture("identity_labels_aliases.json"), "2026-05-16T10:05:00+00:00"),
    ]
    entity_payloads = {"Q12345": (read_fixture("entity_Q12345.json"), "2026-05-16T10:10:00+00:00")}

    bundle = transform_wikidata_payloads(sparql_payloads, entity_payloads)

    assert len(bundle.source_games) == 1
    assert len(bundle.source_game_aliases) >= 3
    assert len(bundle.source_game_external_ids) == 3
    assert len(bundle.source_game_urls) == 2

    game_row = bundle.source_games[0]
    assert game_row["source"] == "wikidata"
    assert game_row["source_game_id"] == "Q12345"
    assert game_row["name"] == "Игра Пример"
    assert game_row["release_year"] == 2013


def test_transform_uses_sparql_only_when_entity_data_missing() -> None:
    sparql_payloads = [
        (read_fixture("identity_external_ids.json"), "2026-05-16T10:00:00+00:00"),
        (read_fixture("identity_labels_aliases.json"), "2026-05-16T10:05:00+00:00"),
    ]

    bundle = transform_wikidata_payloads(sparql_payloads, {})

    assert len(bundle.source_games) == 1
    assert len(bundle.source_game_external_ids) == 3
    assert bundle.source_game_urls[0]["url_type"] in {"ruwiki", "enwiki"}
