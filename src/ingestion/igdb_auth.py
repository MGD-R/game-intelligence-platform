"""IGDB OAuth2 token helpers with safe dry-run support."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from src.ingestion.redaction import REDACTED
from src.utils.config import load_yaml_config

TOKEN_URL = "https://id.twitch.tv/oauth2/token"


def load_igdb_settings() -> dict[str, Any]:
    return load_yaml_config("sources").get("sources", {}).get("igdb", {})


def resolve_igdb_credentials() -> tuple[str, str, str] | None:
    settings = load_igdb_settings()
    primary_id = str(settings.get("client_id_env", "IGDB_CLIENT_ID"))
    primary_secret = str(settings.get("client_secret_env", "IGDB_CLIENT_SECRET"))
    fallback_id = str(settings.get("fallback_client_id_env", "TWITCH_CLIENT_ID"))
    fallback_secret = str(settings.get("fallback_client_secret_env", "TWITCH_CLIENT_SECRET"))

    primary_pair = (os.getenv(primary_id), os.getenv(primary_secret))
    if all(primary_pair):
        return str(primary_pair[0]), str(primary_pair[1]), "primary"

    fallback_pair = (os.getenv(fallback_id), os.getenv(fallback_secret))
    if all(fallback_pair):
        return str(fallback_pair[0]), str(fallback_pair[1]), "fallback"

    return None


@dataclass(slots=True)
class IGDBAccessToken:
    access_token: str
    expires_at: datetime

    def valid(self) -> bool:
        return datetime.now(UTC) < self.expires_at


class IGDBTokenProvider:
    def __init__(self) -> None:
        self._token: IGDBAccessToken | None = None

    def token_request_metadata(self) -> dict[str, object]:
        settings = load_igdb_settings()
        return {
            "token_url": TOKEN_URL,
            "client_id_env": settings.get("client_id_env", "IGDB_CLIENT_ID"),
            "client_secret_env": REDACTED,
            "fallback_client_id_env": settings.get("fallback_client_id_env", "TWITCH_CLIENT_ID"),
            "fallback_client_secret_env": REDACTED,
        }

    def get_access_token(self, *, dry_run: bool = False, force_refresh: bool = False) -> str:
        if dry_run:
            return "<dry-run-token>"
        if not force_refresh and self._token and self._token.valid():
            return self._token.access_token

        credentials = resolve_igdb_credentials()
        if credentials is None:
            raise RuntimeError(
                "IGDB credentials are not configured. Set IGDB_CLIENT_ID/IGDB_CLIENT_SECRET "
                "or TWITCH_CLIENT_ID/TWITCH_CLIENT_SECRET."
            )
        client_id, client_secret, _ = credentials

        response = httpx.post(
            TOKEN_URL,
            params={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        access_token = str(payload.get("access_token") or "")
        expires_in = int(payload.get("expires_in") or 0)
        if not access_token or expires_in <= 0:
            raise RuntimeError("IGDB token response did not include a usable access token.")
        self._token = IGDBAccessToken(
            access_token=access_token,
            expires_at=datetime.now(UTC) + timedelta(seconds=max(1, expires_in - 60)),
        )
        return self._token.access_token


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IGDB auth helper.")
    parser.add_argument("--dry-run", action="store_true", help="Preview auth flow only.")
    parser.add_argument("--force-refresh", action="store_true", help="Force token refresh.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    provider = IGDBTokenProvider()
    if args.dry_run:
        print(provider.token_request_metadata())
        return 0

    token = provider.get_access_token(force_refresh=args.force_refresh)
    print({"token_acquired": bool(token), "token_preview": REDACTED})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
