"""Wikipedia client built on top of the shared ingestion framework."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from src.ingestion.base_client import BaseAPIClient, IngestionResponse
from src.ingestion.cli import build_common_parser
from src.ingestion.repository import IngestionRepository
from src.utils.config import load_yaml_config


def load_wikipedia_settings() -> dict[str, Any]:
    return load_yaml_config("sources").get("sources", {}).get("wikipedia", {})


@dataclass(slots=True)
class WikipediaClient(BaseAPIClient):
    source: str = "wikipedia"
    base_url: str = "https://en.wikipedia.org/api/rest_v1"
    rest_base_url_template: str = "https://{lang}.wikipedia.org/api/rest_v1"
    action_api_url_template: str = "https://{lang}.wikipedia.org/w/api.php"
    user_agent_env: str = "WIKIMEDIA_USER_AGENT"
    timeout_seconds: int = 10
    source_settings: dict[str, object] = field(default_factory=load_wikipedia_settings)
    repository: IngestionRepository | None = field(default_factory=IngestionRepository)

    def __post_init__(self) -> None:
        if self.source_settings:
            self.base_url = str(self.source_settings.get("base_url", self.base_url))
            self.rest_base_url_template = str(
                self.source_settings.get(
                    "rest_base_url_template",
                    self.rest_base_url_template,
                )
            )
            self.action_api_url_template = str(
                self.source_settings.get(
                    "action_api_url_template",
                    self.action_api_url_template,
                )
            )
            self.user_agent_env = str(
                self.source_settings.get("user_agent_env", self.user_agent_env)
            )
            self.timeout_seconds = int(
                self.source_settings.get("timeout_seconds", self.timeout_seconds)
            )
        BaseAPIClient.__post_init__(self)

    def user_agent(self, *, required: bool) -> str:
        value = os.getenv(self.user_agent_env)
        if value:
            return value
        if required:
            raise RuntimeError(f"Missing required Wikimedia user agent env: {self.user_agent_env}")
        return "<missing-user-agent>"

    def encode_title(self, title: str) -> str:
        return quote(title.replace(" ", "_"), safe="")

    def get_page_summary(
        self,
        lang: str,
        title: str,
        *,
        dry_run: bool = False,
        force_refresh: bool = False,
        from_cache_only: bool = False,
    ) -> IngestionResponse:
        base_url = self.rest_base_url_template.format(lang=lang)
        endpoint = f"{base_url.rstrip('/')}/page/summary/{self.encode_title(title)}"
        return self.request(
            "GET",
            endpoint,
            headers={
                "Accept": "application/json",
                "User-Agent": self.user_agent(required=not dry_run),
            },
            dry_run=dry_run,
            force_refresh=force_refresh,
            from_cache_only=from_cache_only,
            use_cache=bool(self.source_settings.get("cache_enabled", True)),
        )

    def get_page_extract(
        self,
        lang: str,
        title: str,
        *,
        dry_run: bool = False,
        force_refresh: bool = False,
        from_cache_only: bool = False,
    ) -> IngestionResponse:
        endpoint = self.action_api_url_template.format(lang=lang)
        return self.request(
            "GET",
            endpoint,
            params={
                "action": "query",
                "prop": "extracts",
                "exintro": 1,
                "explaintext": 1,
                "titles": title,
                "format": "json",
            },
            headers={
                "Accept": "application/json",
                "User-Agent": self.user_agent(required=not dry_run),
            },
            dry_run=dry_run,
            force_refresh=force_refresh,
            from_cache_only=from_cache_only,
            use_cache=bool(self.source_settings.get("cache_enabled", True)),
        )


def build_parser() -> argparse.ArgumentParser:
    parser = build_common_parser("Wikipedia client helper commands.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run a safe Wikipedia request preview.",
    )
    parser.add_argument("--language", default="en", help="Language to use in check mode.")
    parser.add_argument("--title", default="Minecraft", help="Page title to use in check mode.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.check:
        print("Use --check to run a safe Wikipedia client preview.")
        return 0

    client = WikipediaClient(repository=None if args.dry_run else IngestionRepository())
    response = client.get_page_summary(
        args.language,
        args.title,
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
