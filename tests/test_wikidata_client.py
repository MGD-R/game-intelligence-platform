from __future__ import annotations

import pytest

from src.ingestion.wikidata_client import WikidataClient
from src.ingestion.wikidata_queries import build_query


def test_wikidata_dry_run_redacts_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WIKIMEDIA_USER_AGENT", "game-intelligence-platform/0.1 (me@example.com)")
    client = WikidataClient(repository=None)

    response = client.run_sparql(
        build_query("external_ids_sitelinks", limit=1),
        query_name="external_ids_sitelinks",
        dry_run=True,
    )

    assert response.dry_run is True
    assert response.request_metadata["headers"]["User-Agent"] == "***REDACTED***"
    assert response.request_metadata["headers"]["Accept"] == "application/sparql-results+json"


def test_wikidata_request_hash_is_stable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WIKIMEDIA_USER_AGENT", "game-intelligence-platform/0.1 (me@example.com)")
    client = WikidataClient(repository=None)
    query = build_query("external_ids_sitelinks", limit=1)

    first = client.run_sparql(query, query_name="external_ids_sitelinks", dry_run=True)
    second = client.run_sparql(query, query_name="external_ids_sitelinks", dry_run=True)

    assert first.request_hash == second.request_hash


def test_entity_data_requires_user_agent_outside_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WIKIMEDIA_USER_AGENT", raising=False)
    client = WikidataClient(repository=None)

    with pytest.raises(RuntimeError, match="Missing required Wikimedia user agent env"):
        client.get_entity_data("Q12345")
