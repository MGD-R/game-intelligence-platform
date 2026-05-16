from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ingestion.rawg_client import RawgClient

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "rawg"


def read_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_rawg_games_dry_run_redacts_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAWG_API_KEY", raising=False)
    client = RawgClient(repository=None)

    response = client.get_games(
        page=2,
        page_size=5,
        ordering="-added",
        dry_run=True,
    )

    assert response.dry_run is True
    assert response.request_metadata["params"]["key"] == "***REDACTED***"
    assert response.request_metadata["params"]["page"] == 2
    assert response.request_metadata["params"]["page_size"] == 5
    assert response.request_metadata["params"]["ordering"] == "-added"


def test_rawg_details_requires_api_key_outside_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAWG_API_KEY", raising=False)
    client = RawgClient(repository=None)

    with pytest.raises(RuntimeError, match="Missing required RAWG credential env"):
        client.get_game_details(3498)


def test_rawg_reference_dry_run_is_dict_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAWG_API_KEY", "secret")
    client = RawgClient(repository=None)

    response = client.get_genres(dry_run=True, page_size=3)

    assert isinstance(response.payload, dict)
    assert response.request_metadata["params"]["key"] == "***REDACTED***"
    assert response.request_metadata["params"]["page_size"] == 3


def test_rawg_fixture_shape_stays_stable() -> None:
    index_payload = read_fixture("index_page.json")

    assert index_payload["count"] == 1
    assert isinstance(index_payload["results"], list)
