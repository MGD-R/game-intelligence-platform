from __future__ import annotations

import pytest

from src.ingestion.http import should_retry_response
from src.ingestion.steam_client import SteamClient


def test_steam_appdetails_dry_run_builds_expected_request() -> None:
    client = SteamClient(repository=None)

    response = client.get_app_details("271590", dry_run=True)

    assert response.dry_run is True
    assert response.request_metadata["params"]["appids"] == "271590"
    assert response.request_metadata["params"]["l"] == "russian"
    assert response.request_metadata["params"]["cc"] == "ru"


def test_steam_request_hash_is_stable() -> None:
    client = SteamClient(repository=None)

    first = client.get_app_details("271590", dry_run=True)
    second = client.get_app_details("271590", dry_run=True)

    assert first.request_hash == second.request_hash


def test_steam_store_appdetails_does_not_require_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("STEAM_API_KEY", raising=False)
    client = SteamClient(repository=None)

    response = client.get_app_details("271590", dry_run=True)

    assert response.request_metadata["params"]["appids"] == "271590"


def test_steam_403_is_not_retryable() -> None:
    assert should_retry_response("steam", 403) is False
