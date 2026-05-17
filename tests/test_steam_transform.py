from __future__ import annotations

import json
from pathlib import Path

from src.preprocessing.steam_to_staging import transform_steam_payloads

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "steam"


def read_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_steam_fixture_maps_to_staging_rows() -> None:
    bundle = transform_steam_payloads(
        [("271590", read_fixture("appdetails_271590.json"), "2026-01-01T00:00:00+00:00")]
    )

    assert bundle.source_games[0]["source"] == "steam"
    assert bundle.source_games[0]["source_game_id"] == "271590"
    assert bundle.source_games[0]["release_year"] == 2015
    assert any(row["genre_name"] == "Action" for row in bundle.source_game_genres)
    assert any(row["tag_name"] == "Single-player" for row in bundle.source_game_tags)
    assert any(row["company_role"] == "developer" for row in bundle.source_game_companies)
    assert any(row["rating_type"] == "steam_metacritic" for row in bundle.source_game_ratings)
    assert any(
        row["metric_name"] == "recommendations_total" for row in bundle.source_game_popularity
    )
