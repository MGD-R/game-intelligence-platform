from __future__ import annotations

import gzip
import json
from pathlib import Path

from src.preprocessing.export_data_pack import main as export_data_pack_main


class _ExportRepoStub:
    def fetch_raw_rows(self, table_name: str) -> list[dict[str, object]]:
        if table_name == "raw.rawg_game_index":
            return [{"endpoint": "/games", "request_hash": "abc", "response_json": {"id": 1}}]
        if table_name == "raw.rawg_game_details":
            return [
                {"endpoint": "/games/1", "request_hash": "details-1", "response_json": {"id": 1}}
            ]
        if table_name == "raw.wikidata_entities":
            return [
                {
                    "endpoint": "/entity/Q1",
                    "request_hash": "entity-1",
                    "response_json": {"id": "Q1"},
                }
            ]
        return []

    def count_api_requests(self, source: str) -> int:
        return {"rawg": 1, "wikidata": 1, "steam": 1}.get(source, 0)

    def count_rows(self, table_name: str, *, source: str | None = None) -> int:
        total_counts = {
            "raw.rawg_game_index": 1,
            "raw.rawg_game_details": 1,
            "raw.wikidata_entities": 1,
            "stg.source_games": 2,
            "stg.source_game_external_ids": 1,
            "ml.entity_candidate_pairs": 1,
            "ml.entity_resolution_features": 1,
            "dm.canonical_games": 1,
            "dm.canonical_game_sources": 2,
            "dm.canonical_game_aliases": 1,
            "dm.canonical_game_external_ids": 1,
        }
        source_counts = {
            ("raw.rawg_game_index", "rawg"): 1,
            ("raw.rawg_game_details", "rawg"): 1,
            ("raw.wikidata_entities", "wikidata"): 1,
            ("stg.source_games", "steam"): 0,
            ("stg.source_games", "wikipedia"): 0,
            ("stg.source_games", "igdb"): 0,
        }
        if source is not None:
            return source_counts.get((table_name, source), 0)
        return total_counts.get(table_name, 0)


def test_export_data_pack_writes_jsonl_and_checksums(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from src.preprocessing import export_data_pack as module

    processed_dir = tmp_path / "project" / "data" / "processed"
    reports_dir = tmp_path / "project" / "data" / "artifacts" / "reports"
    processed_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(module, "project_root", lambda: tmp_path / "project")
    monkeypatch.setattr(module, "IngestionRepository", lambda: _ExportRepoStub())

    output_dir = tmp_path / "pack"
    assert export_data_pack_main(["--output", str(output_dir)]) == 0

    exported = output_dir / "raw" / "jsonl" / "rawg_game_index.jsonl.gz"
    assert exported.exists()
    assert (output_dir / "raw" / "jsonl" / "rawg_game_details.jsonl.gz").exists()
    assert (output_dir / "raw" / "jsonl" / "wikidata_entities.jsonl.gz").exists()
    with gzip.open(exported, "rt", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    assert rows[0]["request_hash"] == "abc"
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "raw/jsonl/rawg_game_index.jsonl.gz" in manifest["checksums"]
    assert manifest["active_sources"] == ["rawg", "wikidata"]
    assert manifest["checked_sources"] == ["steam"]
    assert manifest["optional_sources"] == ["wikipedia", "igdb"]
    assert manifest["run_status"] in {"completed", "partial", "failed"}
    assert "ml_ready" in manifest
    assert (output_dir / "checksums.sha256").exists()
