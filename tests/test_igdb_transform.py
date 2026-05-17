from __future__ import annotations

import json
from pathlib import Path

from src.preprocessing.igdb_to_staging import transform_igdb_payloads

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "igdb"


def read_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_igdb_fixture_maps_to_staging_rows() -> None:
    bundle = transform_igdb_payloads(
        [(read_fixture("game_response.json"), "2026-01-01T00:00:00+00:00")]
    )

    assert bundle.source_games[0]["source"] == "igdb"
    assert bundle.source_games[0]["release_year"] == 2013
    assert any(row["theme_name"] == "Open world" for row in bundle.source_game_themes)
    assert any(row["tag_name"] == "Crime" for row in bundle.source_game_tags)
    assert any(row["company_role"] == "developer" for row in bundle.source_game_companies)
    assert any(row["external_source"] == "steam" for row in bundle.source_game_external_ids)
