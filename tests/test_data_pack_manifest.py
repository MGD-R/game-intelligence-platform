from __future__ import annotations

from pathlib import Path

from src.preprocessing.data_pack_manifest import build_data_pack_manifest, write_manifest


class _RepoStub:
    def count_rows(self, table_name: str, *, source: str | None = None) -> int:
        counts = {
            "raw.rawg_game_index": 2,
            "stg.source_games": 3,
            "ml.entity_candidate_pairs": 1,
        }
        return counts.get(table_name, 0)


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
    assert "secret" not in str(manifest).lower()
    assert manifest_path.exists()
