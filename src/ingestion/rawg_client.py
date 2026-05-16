"""RAWG client built on top of the shared ingestion framework."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from typing import Any

from src.ingestion.base_client import BaseAPIClient, IngestionResponse
from src.ingestion.cli import build_common_parser
from src.ingestion.repository import IngestionRepository
from src.utils.config import load_yaml_config


def load_rawg_settings() -> dict[str, Any]:
    return load_yaml_config("sources").get("sources", {}).get("rawg", {})


@dataclass(slots=True)
class RawgClient(BaseAPIClient):
    api_key_env: str = "RAWG_API_KEY"
    source: str = "rawg"
    base_url: str = "https://api.rawg.io/api"
    timeout_seconds: int = 10
    source_settings: dict[str, object] = field(default_factory=load_rawg_settings)
    repository: IngestionRepository | None = field(default_factory=IngestionRepository)

    def __post_init__(self) -> None:
        if self.source_settings:
            self.base_url = str(self.source_settings.get("base_url", self.base_url))
            self.timeout_seconds = int(
                self.source_settings.get("timeout_seconds", self.timeout_seconds)
            )
            self.api_key_env = str(self.source_settings.get("api_key_env", self.api_key_env))
        BaseAPIClient.__post_init__(self)

    def api_key(self, *, required: bool) -> str:
        value = os.getenv(self.api_key_env)
        if value:
            return value
        if required:
            raise RuntimeError(f"Missing required RAWG credential env: {self.api_key_env}")
        return "<missing-api-key>"

    def get_games(
        self,
        *,
        page: int = 1,
        page_size: int | None = None,
        ordering: str | None = None,
        dates: str | None = None,
        platforms: str | None = None,
        genres: str | None = None,
        dry_run: bool = False,
        from_cache_only: bool = False,
        force_refresh: bool = False,
    ) -> IngestionResponse:
        params: dict[str, object] = {
            "page": page,
            "page_size": page_size
            or int(self.source_settings.get("default_page_size", 40)),
            "key": self.api_key(required=not dry_run),
        }
        if ordering:
            params["ordering"] = ordering
        if dates:
            params["dates"] = dates
        if platforms:
            params["platforms"] = platforms
        if genres:
            params["genres"] = genres
        return self.request(
            "GET",
            "/games",
            params=params,
            dry_run=dry_run,
            from_cache_only=from_cache_only,
            force_refresh=force_refresh,
        )

    def get_game_details(
        self,
        game_id: int | str,
        *,
        dry_run: bool = False,
        from_cache_only: bool = False,
        force_refresh: bool = False,
    ) -> IngestionResponse:
        return self.request(
            "GET",
            f"/games/{game_id}",
            params={"key": self.api_key(required=not dry_run)},
            dry_run=dry_run,
            from_cache_only=from_cache_only,
            force_refresh=force_refresh,
        )

    def get_genres(self, **kwargs: Any) -> IngestionResponse:
        return self._get_reference("/genres", **kwargs)

    def get_platforms(self, **kwargs: Any) -> IngestionResponse:
        return self._get_reference("/platforms", **kwargs)

    def get_stores(self, **kwargs: Any) -> IngestionResponse:
        return self._get_reference("/stores", **kwargs)

    def get_tags(self, **kwargs: Any) -> IngestionResponse:
        return self._get_reference("/tags", **kwargs)

    def _get_reference(
        self,
        endpoint: str,
        *,
        page_size: int | None = None,
        dry_run: bool = False,
        from_cache_only: bool = False,
        force_refresh: bool = False,
    ) -> IngestionResponse:
        return self.request(
            "GET",
            endpoint,
            params={
                "page_size": page_size
                or int(self.source_settings.get("default_page_size", 40)),
                "key": self.api_key(required=not dry_run),
            },
            dry_run=dry_run,
            from_cache_only=from_cache_only,
            force_refresh=force_refresh,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = build_common_parser("RAWG client helper commands.")
    parser.add_argument("--check", action="store_true", help="Run a safe RAWG request preview.")
    parser.add_argument("--page-size", type=int, default=1, help="Page size for check mode.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.check:
        print("Use --check to run a safe RAWG client preview.")
        return 0

    client = RawgClient()
    response = client.get_games(
        page=1,
        page_size=max(1, args.page_size),
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
