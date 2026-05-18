from __future__ import annotations

import json
from pathlib import Path

from src.preprocessing.igdb_search_to_candidates import extract_candidate_rows
from src.preprocessing.igdb_to_staging import load_igdb_payloads, transform_igdb_payloads

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


def test_load_igdb_payloads_deduplicates_same_game_id() -> None:
    payload = read_fixture("game_response.json")
    rows = load_igdb_payloads(
        type(
            "RepoStub",
            (),
            {
                "fetch_raw_rows": lambda self, table_name: [
                    {"response_json": payload, "loaded_at": "2026-01-01T00:00:00+00:00"},
                    {"response_json": payload, "loaded_at": "2026-01-02T00:00:00+00:00"},
                ]
            },
        )()
    )
    assert len(rows) == 1


def test_extract_igdb_search_candidates_keeps_best_rank() -> None:
    candidate = read_fixture("game_response.json")
    raw_rows = [
        {
            "request_hash": "hash-1",
            "response_json": {
                "anchor": {"source": "rawg", "source_game_id": "1", "release_year": 2013},
                "query": {"text": "Grand Theft Auto V", "strategy": "source_name", "rank": 2},
                "candidate": candidate,
            },
        },
        {
            "request_hash": "hash-2",
            "response_json": {
                "anchor": {"source": "rawg", "source_game_id": "1", "release_year": 2013},
                "query": {"text": "GTA 5", "strategy": "wikidata_alias", "rank": 1},
                "candidate": candidate,
            },
        },
    ]
    rows = extract_candidate_rows(raw_rows)
    assert len(rows) == 1
    assert rows[0].search_rank == 1
    assert rows[0].query_strategy == "wikidata_alias"
