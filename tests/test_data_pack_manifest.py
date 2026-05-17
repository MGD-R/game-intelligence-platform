from __future__ import annotations

from pathlib import Path

from src.preprocessing.data_pack_manifest import build_data_pack_manifest, write_manifest


class _RepoStub:
    def count_api_requests(self, source: str) -> int:
        return {"rawg": 2, "wikidata": 1}.get(source, 0)

    def count_rows(self, table_name: str, *, source: str | None = None) -> int:
        counts = {
            "raw.rawg_game_index": 2,
            "raw.rawg_game_details": 4,
            "raw.rawg_reference_data": 1,
            "raw.wikidata_sparql_results": 1,
            "raw.wikidata_entities": 5,
            "stg.source_games": 3 if source is None else {"rawg": 2, "wikidata": 1}.get(source, 0),
            "stg.source_game_external_ids": 6,
            "ml.entity_candidate_pairs": 1,
            "ml.entity_resolution_features": 1,
        }
        return counts.get(table_name, 0)

    def fetch_staging_rows(
        self,
        table_name: str,
        *,
        source: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        if table_name != "stg.source_game_external_ids" or source != "wikidata":
            return []
        rows = [
            {
                "source": "wikidata",
                "source_game_id": "Q1",
                "external_source": "rawg",
                "external_id": "1",
            }
        ]
        return rows if limit is None else rows[:limit]


def test_data_pack_manifest_has_expected_fields(tmp_path: Path) -> None:
    processed_dir = tmp_path / "processed"
    reports_dir = tmp_path / "reports"
    processed_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "source_games.parquet",
        "source_aliases.parquet",
        "source_external_ids.parquet",
        "entity_candidate_pairs.parquet",
        "entity_resolution_feature_base.parquet",
    ):
        (processed_dir / name).write_text("ok", encoding="utf-8")
    for name in ("dq_summary.json", "source_coverage.csv", "data_stage_summary.md"):
        (reports_dir / name).write_text("ok", encoding="utf-8")

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
    assert "checksums" in manifest
    assert manifest["run_status"] == "completed"
    assert manifest["ml_ready"] is True
    assert "feature_base" in manifest["completed_steps"]
    assert manifest["failed_steps"] == []
    assert "secret" not in str(manifest).lower()
    assert manifest_path.exists()
