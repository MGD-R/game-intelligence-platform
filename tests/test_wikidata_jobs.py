from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.ingestion.base_client import IngestionResponse
from src.ingestion.jobs import load_wikidata_entities, load_wikidata_identity


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


class FakeWikidataClient:
    def __init__(self) -> None:
        self.repository = object()
        self.source_settings = {"demo_limit": 5000}

    def run_sparql(self, query: str, *, query_name: str, **_: Any) -> IngestionResponse:
        return IngestionResponse(
            source="wikidata",
            endpoint="https://query.wikidata.org/sparql",
            request_hash=f"hash-{query_name}",
            request_url="https://query.wikidata.org/sparql",
            http_status=None,
            payload={"planned_request": {"query_name": query_name, "query": query}},
            response_hash=None,
            from_cache=False,
            dry_run=True,
            cache_path=None,
            request_metadata={"query_name": query_name},
        )

    def get_entity_data(self, qid: str, **_: Any) -> IngestionResponse:
        return IngestionResponse(
            source="wikidata",
            endpoint=f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json",
            request_hash=f"hash-{qid}",
            request_url=f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json",
            http_status=None,
            payload={"planned_request": {"qid": qid}},
            response_hash=None,
            from_cache=False,
            dry_run=True,
            cache_path=None,
            request_metadata={"qid": qid},
        )


def test_load_wikidata_identity_dry_run(monkeypatch, capsys) -> None:
    logger = FakeLogger()
    monkeypatch.setattr(load_wikidata_identity, "WikidataClient", FakeWikidataClient)
    monkeypatch.setattr(load_wikidata_identity, "PipelineRunLogger", lambda **_: logger)

    exit_code = load_wikidata_identity.main(["--dry-run", "--limit", "1"])

    assert exit_code == 0
    assert logger.finished == {
        "status": "completed",
        "metrics": {"query_count": 2, "limit": 1},
        "error_message": None,
    }
    assert capsys.readouterr().out.count("query_name") >= 2


def test_load_wikidata_entities_default_limit_is_zero(monkeypatch, capsys, tmp_path) -> None:
    logger = FakeLogger()
    qids_file = tmp_path / "qids.txt"
    qids_file.write_text("Q12345\nQ23456\n", encoding="utf-8")
    monkeypatch.setattr(load_wikidata_entities, "WikidataClient", FakeWikidataClient)
    monkeypatch.setattr(load_wikidata_entities, "PipelineRunLogger", lambda **_: logger)

    exit_code = load_wikidata_entities.main(["--dry-run", "--qids-file", str(qids_file)])

    assert exit_code == 0
    assert logger.finished == {
        "status": "completed",
        "metrics": {"requested_qids": 0},
        "error_message": None,
    }
    assert capsys.readouterr().out == ""


def test_load_wikidata_entities_with_limit(monkeypatch, capsys, tmp_path) -> None:
    logger = FakeLogger()
    qids_file = tmp_path / "qids.txt"
    qids_file.write_text("Q12345\nQ23456\n", encoding="utf-8")
    monkeypatch.setattr(load_wikidata_entities, "WikidataClient", FakeWikidataClient)
    monkeypatch.setattr(load_wikidata_entities, "PipelineRunLogger", lambda **_: logger)

    exit_code = load_wikidata_entities.main(
        ["--dry-run", "--qids-file", str(qids_file), "--limit", "1"]
    )

    assert exit_code == 0
    assert logger.finished == {
        "status": "completed",
        "metrics": {"requested_qids": 1},
        "error_message": None,
    }
    assert "Q12345" in capsys.readouterr().out
