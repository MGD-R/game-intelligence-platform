from __future__ import annotations

import pytest

from src.ingestion.wikipedia_client import WikipediaClient


def test_wikipedia_summary_dry_run_builds_expected_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WIKIMEDIA_USER_AGENT", "game-intelligence-platform/0.1 (me@example.com)")
    client = WikipediaClient(repository=None)

    response = client.get_page_summary("ru", "Пример игры", dry_run=True)

    assert response.dry_run is True
    assert response.request_metadata["url"].startswith(
        "https://ru.wikipedia.org/api/rest_v1/page/summary/"
    )
    assert (
        "%D0%9F%D1%80%D0%B8%D0%BC%D0%B5%D1%80_%D0%B8%D0%B3%D1%80%D1%8B"
        in response.request_metadata["url"]
    )
    assert response.request_metadata["headers"]["User-Agent"] == "***REDACTED***"


def test_wikipedia_request_hash_is_stable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WIKIMEDIA_USER_AGENT", "game-intelligence-platform/0.1 (me@example.com)")
    client = WikipediaClient(repository=None)

    first = client.get_page_summary("en", "Sample Game", dry_run=True)
    second = client.get_page_summary("en", "Sample Game", dry_run=True)

    assert first.request_hash == second.request_hash


def test_wikipedia_extract_requires_user_agent_outside_dry_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WIKIMEDIA_USER_AGENT", raising=False)
    client = WikipediaClient(repository=None)

    with pytest.raises(RuntimeError, match="Missing required Wikimedia user agent env"):
        client.get_page_extract("en", "Sample Game")
