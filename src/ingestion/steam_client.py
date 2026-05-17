"""Steam client built on top of the shared ingestion framework."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Any

from src.ingestion.base_client import BaseAPIClient, IngestionResponse
from src.ingestion.cli import build_common_parser
from src.ingestion.repository import IngestionRepository
from src.utils.config import load_yaml_config


def load_steam_settings() -> dict[str, Any]:
    return load_yaml_config("sources").get("sources", {}).get("steam", {})


@dataclass(slots=True)
class SteamClient(BaseAPIClient):
    source: str = "steam"
    base_url: str = "https://store.steampowered.com/api"
    web_api_base_url: str = "https://api.steampowered.com"
    partner_api_base_url: str = "https://partner.steam-api.com"
    api_key_env: str = "STEAM_API_KEY"
    default_language: str = "russian"
    default_country: str = "ru"
    timeout_seconds: int = 10
    source_settings: dict[str, object] = field(default_factory=load_steam_settings)
    repository: IngestionRepository | None = field(default_factory=IngestionRepository)

    def __post_init__(self) -> None:
        if self.source_settings:
            self.base_url = str(self.source_settings.get("store_api_base_url", self.base_url))
            self.web_api_base_url = str(
                self.source_settings.get("web_api_base_url", self.web_api_base_url)
            )
            self.partner_api_base_url = str(
                self.source_settings.get(
                    "partner_api_base_url",
                    self.partner_api_base_url,
                )
            )
            self.api_key_env = str(self.source_settings.get("api_key_env", self.api_key_env))
            self.default_language = str(
                self.source_settings.get("default_language", self.default_language)
            )
            self.default_country = str(
                self.source_settings.get("default_country", self.default_country)
            )
            self.timeout_seconds = int(
                self.source_settings.get("timeout_seconds", self.timeout_seconds)
            )
        BaseAPIClient.__post_init__(self)

    def get_app_details(
        self,
        appid: int | str,
        *,
        language: str = "russian",
        country: str = "ru",
        dry_run: bool = False,
        force_refresh: bool = False,
        from_cache_only: bool = False,
    ) -> IngestionResponse:
        return self.request(
            "GET",
            "/appdetails",
            params={
                "appids": str(appid),
                "l": language or self.default_language,
                "cc": country or self.default_country,
            },
            dry_run=dry_run,
            force_refresh=force_refresh,
            from_cache_only=from_cache_only,
            use_cache=bool(self.source_settings.get("cache_enabled", True)),
        )

    def get_app_list(
        self,
        *,
        dry_run: bool = False,
        force_refresh: bool = False,
        from_cache_only: bool = False,
        disabled_by_default: bool = True,
    ) -> IngestionResponse:
        if disabled_by_default and not dry_run:
            raise RuntimeError("Steam app list is disabled by default for the MVP.")
        return self.request(
            "GET",
            f"{self.web_api_base_url.rstrip('/')}/ISteamApps/GetAppList/v2/",
            dry_run=dry_run,
            force_refresh=force_refresh,
            from_cache_only=from_cache_only,
            use_cache=bool(self.source_settings.get("cache_enabled", True)),
        )


def build_parser() -> argparse.ArgumentParser:
    parser = build_common_parser("Steam client helper commands.")
    parser.add_argument("--check", action="store_true", help="Run a safe Steam request preview.")
    parser.add_argument(
        "--app-id",
        default="271590",
        help="Steam AppID to use in check mode.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.check:
        print("Use --check to run a safe Steam client preview.")
        return 0

    client = SteamClient(repository=None if args.dry_run else IngestionRepository())
    response = client.get_app_details(
        args.app_id,
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
