from __future__ import annotations

from src.ingestion.igdb_auth import IGDBTokenProvider, resolve_igdb_credentials


def test_igdb_auth_dry_run_metadata_is_redacted() -> None:
    metadata = IGDBTokenProvider().token_request_metadata()
    assert metadata["client_secret_env"] == "***REDACTED***"
    assert metadata["fallback_client_secret_env"] == "***REDACTED***"


def test_igdb_credentials_support_fallback(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("IGDB_CLIENT_ID", raising=False)
    monkeypatch.delenv("IGDB_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("TWITCH_CLIENT_ID", "client")
    monkeypatch.setenv("TWITCH_CLIENT_SECRET", "secret")
    credentials = resolve_igdb_credentials()
    assert credentials is not None
    assert credentials[2] == "fallback"
