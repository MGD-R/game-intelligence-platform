from __future__ import annotations

from pathlib import Path

from src.preprocessing.data_pack_manifest import build_data_pack_manifest, write_manifest


class _RepoStub:
    def count_api_requests(self, source: str) -> int:
        return {"rawg": 2, "wikidata": 1, "steam": 1}.get(source, 0)

    def count_rows(self, table_name: str, *, source: str | None = None) -> int:
        source_counts = {
            ("raw.rawg_game_index", "rawg"): 2,
            ("raw.rawg_game_details", "rawg"): 4,
            ("raw.wikidata_entities", "wikidata"): 5,
            ("stg.source_games", "rawg"): 2,
            ("stg.source_games", "wikidata"): 1,
            ("stg.source_games", "steam"): 0,
            ("stg.source_games", "wikipedia"): 0,
            ("stg.source_games", "igdb"): 0,
        }
        total_counts = {
            "raw.rawg_game_index": 2,
            "raw.rawg_game_details": 4,
            "raw.wikidata_entities": 5,
            "stg.source_games": 3,
            "stg.source_game_external_ids": 6,
            "ml.entity_candidate_pairs": 1,
        }
        if source is not None:
            return source_counts.get((table_name, source), 0)
        return total_counts.get(table_name, 0)


def test_data_pack_manifest_has_expected_fields(tmp_path: Path) -> None:
    manifest = build_data_pack_manifest(
        _RepoStub(),
        data_pack_id="gip_demo_2026_05_17",
        pack_root=tmp_path,
        sources=["rawg", "wikidata"],
        warnings=["optional source not loaded: steam"],
    )
    manifest_path = write_manifest(tmp_path / "manifest.json", manifest)

    assert manifest["data_pack_id"] == "gip_demo_2026_05_17"
    assert manifest["row_counts"]["stg.source_games"] == 3
    assert manifest["row_counts"]["raw.rawg_game_details"] == 4
    assert manifest["api_calls_by_source"]["rawg"] == 2
    assert manifest["active_sources"] == ["rawg", "wikidata"]
    assert manifest["checked_sources"] == []
    assert manifest["optional_sources"] == []
    assert "checksums" in manifest
    assert "secret" not in str(manifest).lower()
    assert manifest_path.exists()
