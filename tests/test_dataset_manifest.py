from __future__ import annotations

from pathlib import Path

from src.preprocessing.build_dataset_manifest import build_manifest
from src.preprocessing.export_ml_ready_base import write_parquet


class ManifestRepositoryStub:
    def count_rows(self, table_name: str, *, source: str | None = None) -> int:
        counts = {
            ("stg.source_games", "rawg"): 1,
            ("stg.source_games", "wikidata"): 1,
            ("stg.source_games", "steam"): 0,
            ("stg.source_games", "wikipedia"): 0,
            ("stg.source_games", "igdb"): 0,
        }
        return counts.get((table_name, source), 0)

    def fetch_candidate_pairs(self) -> list[dict[str, object]]:
        return [{"pair_id": "pair-1", "label_value": "1"}]


def test_manifest_contains_counts_and_paths(tmp_path: Path) -> None:
    output_dir = tmp_path / "processed"
    reports_dir = tmp_path / "reports"
    manifest_path = tmp_path / "manifests" / "ml_ready_dataset_manifest.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    write_parquet(output_dir / "source_games.parquet", [{"source": "rawg", "source_game_id": "1"}])

    manifest = build_manifest(
        ManifestRepositoryStub(),
        output_dir=output_dir,
        reports_dir=reports_dir,
        manifest_path=manifest_path,
        warnings=["optional source not loaded: steam"],
    )

    assert manifest["record_counts_per_dataset"]["source_games"] == 1
    assert manifest["candidate_pair_count"] == 1
    assert "steam" in manifest["warnings"][0]
    assert "secret" not in str(manifest).lower()
