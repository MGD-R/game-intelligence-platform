from __future__ import annotations

import gzip
import json
from pathlib import Path

from src.preprocessing.export_data_pack import main as export_data_pack_main


class _ExportRepoStub:
    def fetch_raw_rows(self, table_name: str) -> list[dict[str, object]]:
        if table_name == "raw.rawg_game_index":
            return [{"endpoint": "/games", "request_hash": "abc", "response_json": {"id": 1}}]
        return []

    def count_rows(self, table_name: str, *, source: str | None = None) -> int:
        return 0


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
    with gzip.open(exported, "rt", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    assert rows[0]["request_hash"] == "abc"
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "checksums.sha256").exists()
