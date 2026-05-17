from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.ingestion.base_client import IngestionResponse
from src.ingestion.jobs import load_rawg_details, load_rawg_index, load_rawg_reference


@dataclass
class FakeLogger:
    parameters: dict[str, Any] | None = None
    finished: dict[str, Any] | None = None

    def mark_started(self, parameters: dict[str, Any] | None = None) -> None:
        self.parameters = parameters

    def mark_finished(
        self,
        *,
        status: str,
        metrics: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        self.finished = {
            "status": status,
            "metrics": metrics,
            "error_message": error_message,
        }


class FakeRawgClient:
    def __init__(self) -> None:
        self.repository = object()
        self.source_settings = {"default_page_size": 40, "demo_page_limit": 10}

    def get_games(self, **_: Any) -> IngestionResponse:
        return IngestionResponse(
            source="rawg",
            endpoint="/games",
            request_hash="hash-games",
            request_url="https://api.rawg.io/api/games",
            http_status=None,
            payload={"planned_request": {"url": "https://api.rawg.io/api/games"}},
            response_hash=None,
            from_cache=False,
            dry_run=True,
            cache_path=None,
            request_metadata={"url": "https://api.rawg.io/api/games"},
        )

    def get_game_details(self, game_id: str, **_: Any) -> IngestionResponse:
        return IngestionResponse(
            source="rawg",
            endpoint=f"/games/{game_id}",
            request_hash=f"hash-{game_id}",
            request_url=f"https://api.rawg.io/api/games/{game_id}",
            http_status=None,
            payload={"planned_request": {"url": f"https://api.rawg.io/api/games/{game_id}"}},
            response_hash=None,
            from_cache=False,
            dry_run=True,
            cache_path=None,
            request_metadata={"url": f"https://api.rawg.io/api/games/{game_id}"},
        )

    def get_genres(self, **_: Any) -> IngestionResponse:
        return self._reference("/genres")

    def get_platforms(self, **_: Any) -> IngestionResponse:
        return self._reference("/platforms")

    def get_stores(self, **_: Any) -> IngestionResponse:
        return self._reference("/stores")

    def get_tags(self, **_: Any) -> IngestionResponse:
        return self._reference("/tags")

    @staticmethod
    def _reference(endpoint: str) -> IngestionResponse:
        return IngestionResponse(
            source="rawg",
            endpoint=endpoint,
            request_hash=f"hash-{endpoint}",
            request_url=f"https://api.rawg.io/api{endpoint}",
            http_status=None,
            payload={"planned_request": {"url": f"https://api.rawg.io/api{endpoint}"}},
            response_hash=None,
            from_cache=False,
            dry_run=True,
            cache_path=None,
            request_metadata={"url": f"https://api.rawg.io/api{endpoint}"},
        )


def test_load_rawg_index_dry_run(monkeypatch, capsys) -> None:
    logger = FakeLogger()
    monkeypatch.setattr(load_rawg_index, "RawgClient", FakeRawgClient)
    monkeypatch.setattr(load_rawg_index, "PipelineRunLogger", lambda **_: logger)

    exit_code = load_rawg_index.main(["--dry-run", "--page-limit", "1", "--page-size", "1"])

    assert exit_code == 0
    assert logger.finished == {"status": "completed", "metrics": None, "error_message": None}
    assert "planned" in capsys.readouterr().out


def test_load_rawg_reference_dry_run(monkeypatch, capsys) -> None:
    logger = FakeLogger()
    monkeypatch.setattr(load_rawg_reference, "RawgClient", FakeRawgClient)
    monkeypatch.setattr(load_rawg_reference, "PipelineRunLogger", lambda **_: logger)
    monkeypatch.setattr(
        load_rawg_reference,
        "REFERENCE_LOADERS",
        {
            "genres": lambda client, **kwargs: client.get_genres(**kwargs),
            "platforms": lambda client, **kwargs: client.get_platforms(**kwargs),
            "stores": lambda client, **kwargs: client.get_stores(**kwargs),
            "tags": lambda client, **kwargs: client.get_tags(**kwargs),
        },
    )

    exit_code = load_rawg_reference.main(["--dry-run"])

    assert exit_code == 0
    assert logger.finished == {"status": "completed", "metrics": None, "error_message": None}
    stdout = capsys.readouterr().out
    assert "reference_type" in stdout
    assert stdout.count("planned") == 4


def test_load_rawg_details_dry_run(monkeypatch, capsys, tmp_path) -> None:
    logger = FakeLogger()
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("3498\n4200\n", encoding="utf-8")
    monkeypatch.setattr(load_rawg_details, "RawgClient", FakeRawgClient)
    monkeypatch.setattr(load_rawg_details, "PipelineRunLogger", lambda **_: logger)

    exit_code = load_rawg_details.main(["--dry-run", "--ids-file", str(ids_file), "--limit", "1"])

    assert exit_code == 0
    assert logger.finished == {
        "status": "completed",
        "metrics": {"requested_ids": 1},
        "error_message": None,
    }
    assert "3498" in capsys.readouterr().out


def test_parse_ids_combines_sources(tmp_path) -> None:
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("3498\n4200\n", encoding="utf-8")

    ids = load_rawg_details.parse_ids("1, 2", str(ids_file))

    assert ids == ["1", "2", "3498", "4200"]
