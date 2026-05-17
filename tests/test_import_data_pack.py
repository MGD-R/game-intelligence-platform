from __future__ import annotations

import gzip
import json
from pathlib import Path

from src.preprocessing.import_data_pack import main as import_data_pack_main


class _ImportRepoStub:
    def __init__(self) -> None:
        self.rows: set[tuple[str, str]] = set()

    def import_raw_record(self, *, table_name: str, row: dict[str, object]) -> None:
        self.rows.add((table_name, str(row.get("request_hash") or "")))


def _write_pack(path: Path) -> None:
    raw_dir = path / "raw" / "jsonl"
    raw_dir.mkdir(parents=True, exist_ok=True)
    with gzip.open(raw_dir / "rawg_game_index.jsonl.gz", "wt", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "endpoint": "/games",
                    "request_hash": "abc",
                    "response_json": {"id": 1},
                    "http_status": 200,
                    "from_cache": False,
                }
            )
            + "\n"
        )
    (path / "manifest.json").write_text(json.dumps({"data_pack_id": "pack"}), encoding="utf-8")


def test_import_data_pack_is_idempotent(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from src.preprocessing import import_data_pack as module

    pack_root = tmp_path / "pack"
    _write_pack(pack_root)
    repository = _ImportRepoStub()
    monkeypatch.setattr(module, "IngestionRepository", lambda: repository)

    assert import_data_pack_main(["--input", str(pack_root)]) == 0
    assert import_data_pack_main(["--input", str(pack_root)]) == 0
    assert len(repository.rows) == 1
