from __future__ import annotations

import json
from pathlib import Path

from src.preprocessing.rawg_to_staging import transform_rawg_payloads

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "rawg"


def read_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_transform_rawg_payloads_builds_expected_staging_rows() -> None:
    index_payload = read_fixture("index_page.json")
    details_payload = read_fixture("details_3498.json")

    bundle = transform_rawg_payloads(
        [(index_payload, "2026-05-16T10:00:00+00:00")],
        {"3498": (details_payload, "2026-05-16T10:05:00+00:00")},
    )

    assert len(bundle.source_games) == 1
    assert len(bundle.source_game_genres) == 2
    assert len(bundle.source_game_platforms) == 2
    assert len(bundle.source_game_tags) == 2
    assert len(bundle.source_game_companies) == 2
    assert len(bundle.source_game_descriptions) == 1
    assert len(bundle.source_game_ratings) == 3
    assert len(bundle.source_game_urls) >= 2
    assert len(bundle.source_game_popularity) == 1

    game_row = bundle.source_games[0]
    assert game_row["source"] == "rawg"
    assert game_row["source_game_id"] == "3498"
    assert game_row["name_normalized"] == "grand theft auto v"
    assert game_row["release_year"] == 2013
    assert game_row["is_dlc"] is False
    assert game_row["quality_flags_json"] == {"has_details": True}


def test_transform_uses_index_only_when_details_are_missing() -> None:
    index_payload = read_fixture("index_page.json")

    bundle = transform_rawg_payloads(
        [(index_payload, "2026-05-16T10:00:00+00:00")],
        {},
    )

    assert len(bundle.source_games) == 1
    assert bundle.source_games[0]["quality_flags_json"] == {"has_details": False}
    assert bundle.source_game_companies == []
    assert bundle.source_game_descriptions == []
