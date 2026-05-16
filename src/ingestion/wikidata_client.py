"""Wikidata client built on top of the shared ingestion framework."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from typing import Any

from src.ingestion.base_client import BaseAPIClient, IngestionResponse
from src.ingestion.cli import build_common_parser
from src.ingestion.repository import IngestionRepository
from src.ingestion.wikidata_queries import build_query
from src.utils.config import load_yaml_config


def load_wikidata_settings() -> dict[str, Any]:
    return load_yaml_config("sources").get("sources", {}).get("wikidata", {})


@dataclass(slots=True)
class WikidataClient(BaseAPIClient):
    source: str = "wikidata"
    base_url: str = "https://query.wikidata.org"
    sparql_url: str = "https://query.wikidata.org/sparql"
    entity_data_url: str = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    user_agent_env: str = "WIKIMEDIA_USER_AGENT"
    timeout_seconds: int = 15
    source_settings: dict[str, object] = field(default_factory=load_wikidata_settings)
    repository: IngestionRepository | None = field(default_factory=IngestionRepository)

    def __post_init__(self) -> None:
        if self.source_settings:
            self.base_url = str(self.source_settings.get("base_url", self.base_url))
            self.sparql_url = str(self.source_settings.get("sparql_url", self.sparql_url))
            self.entity_data_url = str(
                self.source_settings.get("entity_data_url", self.entity_data_url)
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
            raise RuntimeError(
                f"Missing required Wikimedia user agent env: {self.user_agent_env}"
            )
        return "<missing-user-agent>"

    def run_sparql(
        self,
        query: str,
        *,
        query_name: str,
        dry_run: bool = False,
        force_refresh: bool = False,
        from_cache_only: bool = False,
    ) -> IngestionResponse:
        return self.request(
            "GET",
            self.sparql_url,
            params={"query": query, "format": "json"},
            headers={
                "Accept": "application/sparql-results+json",
                "User-Agent": self.user_agent(required=not dry_run),
            },
            dry_run=dry_run,
            force_refresh=force_refresh,
            from_cache_only=from_cache_only,
        )

    def get_entity_data(
        self,
        qid: str,
        *,
        dry_run: bool = False,
        force_refresh: bool = False,
        from_cache_only: bool = False,
    ) -> IngestionResponse:
        return self.request(
            "GET",
            self.entity_data_url.format(qid=qid),
            headers={
                "Accept": "application/json",
                "User-Agent": self.user_agent(required=not dry_run),
            },
            dry_run=dry_run,
            force_refresh=force_refresh,
            from_cache_only=from_cache_only,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = build_common_parser("Wikidata client helper commands.")
    parser.add_argument("--check", action="store_true", help="Run a safe Wikidata request preview.")
    parser.add_argument(
        "--query-name",
        default="external_ids_sitelinks",
        help="Named query template to preview in check mode.",
    )
    parser.set_defaults(limit=1)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.check:
        print("Use --check to run a safe Wikidata client preview.")
        return 0

    client = WikidataClient()
    response = client.run_sparql(
        build_query(args.query_name, limit=max(1, args.limit)),
        query_name=args.query_name,
        dry_run=args.dry_run,
        force_refresh=args.force_refresh,
        from_cache_only=args.from_cache_only,
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
