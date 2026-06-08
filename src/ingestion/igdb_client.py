"""IGDB client built on the shared ingestion framework."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field

from src.ingestion.base_client import BaseAPIClient, IngestionResponse
from src.ingestion.cli import build_common_parser
from src.ingestion.igdb_auth import IGDBTokenProvider, load_igdb_settings
from src.ingestion.igdb_queries import (
    FIELDS_GAMES,
    build_games_by_ids_query,
    build_reference_query,
    build_search_games_query,
)
from src.ingestion.repository import IngestionRepository


@dataclass(slots=True)
class IGDBClient(BaseAPIClient):
    source: str = "igdb"
    base_url: str = "https://api.igdb.com/v4"
    timeout_seconds: int = 10
    source_settings: dict[str, object] = field(default_factory=load_igdb_settings)
    repository: IngestionRepository | None = field(default_factory=IngestionRepository)
    token_provider: IGDBTokenProvider = field(default_factory=IGDBTokenProvider)

    def __post_init__(self) -> None:
        if self.source_settings:
            self.base_url = str(self.source_settings.get("base_url", self.base_url))
            self.timeout_seconds = int(
                self.source_settings.get("timeout_seconds", self.timeout_seconds)
            )
        BaseAPIClient.__post_init__(self)

    def auth_headers(self, *, dry_run: bool = False, force_refresh: bool = False) -> dict[str, str]:
        settings = self.source_settings
        if dry_run:
            return {
                "Client-ID": "<dry-run-client-id>",
                "Authorization": "Bearer <dry-run-token>",
                "Accept": "application/json",
            }

        access_token = self.token_provider.get_access_token(force_refresh=force_refresh)
        client_id_env = str(settings.get("client_id_env", "IGDB_CLIENT_ID"))
        fallback_id_env = str(settings.get("fallback_client_id_env", "TWITCH_CLIENT_ID"))
        client_id = os.getenv(client_id_env) or os.getenv(fallback_id_env) or ""
        return {
            "Client-ID": client_id,
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

    def post_apicalypse(
        self,
        endpoint: str,
        query: str,
        *,
        dry_run: bool = False,
        force_refresh: bool = False,
        from_cache_only: bool = False,
    ) -> IngestionResponse:
        return self.request(
            "POST",
            endpoint,
            raw_body=query,
            headers=self.auth_headers(dry_run=dry_run, force_refresh=force_refresh),
            dry_run=dry_run,
            force_refresh=force_refresh,
            from_cache_only=from_cache_only,
            use_cache=bool(self.source_settings.get("cache_enabled", True)),
        )

    def get_games_by_ids(
        self,
        ids: list[int],
        *,
        fields: list[str] | None = None,
        dry_run: bool = False,
        force_refresh: bool = False,
        from_cache_only: bool = False,
    ) -> IngestionResponse:
        return self.post_apicalypse(
            "/games",
            build_games_by_ids_query(ids, fields or FIELDS_GAMES),
            dry_run=dry_run,
            force_refresh=force_refresh,
            from_cache_only=from_cache_only,
        )

    def get_reference(
        self,
        endpoint: str,
        *,
        dry_run: bool = False,
        force_refresh: bool = False,
        from_cache_only: bool = False,
    ) -> IngestionResponse:
        return self.post_apicalypse(
            f"/{endpoint}",
            build_reference_query(endpoint),
            dry_run=dry_run,
            force_refresh=force_refresh,
            from_cache_only=from_cache_only,
        )

    def search_games(
        self,
        query_text: str,
        *,
        fields: list[str] | None = None,
        limit: int = 5,
        release_year: int | None = None,
        year_window: int = 0,
        dry_run: bool = False,
        force_refresh: bool = False,
        from_cache_only: bool = False,
    ) -> IngestionResponse:
        return self.post_apicalypse(
            "/games",
            build_search_games_query(
                query_text,
                fields=fields or FIELDS_GAMES,
                limit=limit,
                release_year=release_year,
                year_window=year_window,
            ),
            dry_run=dry_run,
            force_refresh=force_refresh,
            from_cache_only=from_cache_only,
        )

    def multiquery(
        self,
        queries: list[str],
        *,
        dry_run: bool = False,
        force_refresh: bool = False,
        from_cache_only: bool = False,
    ) -> IngestionResponse:
        return self.post_apicalypse(
            "/multiquery",
            "\n".join(queries),
            dry_run=dry_run,
            force_refresh=force_refresh,
            from_cache_only=from_cache_only,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = build_common_parser("IGDB client helper commands.")
    parser.add_argument("--check", action="store_true", help="Run a safe IGDB request preview.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.check:
        print("Use --check to run a safe IGDB client preview.")
        return 0

    client = IGDBClient(repository=None if args.dry_run else IngestionRepository())
    response = client.get_games_by_ids(
        [1020],
        dry_run=args.dry_run,
        from_cache_only=args.from_cache_only,
        force_refresh=args.force_refresh,
    )
    print(
        {
            "source": response.source,
            "request_hash": response.request_hash,
            "dry_run": response.dry_run,
            "request_metadata": response.request_metadata,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
