"""Wikidata client placeholder."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class WikidataClient:
    base_url: str = "https://www.wikidata.org/w/api.php"
    user_agent_env: str = "WIKIMEDIA_USER_AGENT"

    def describe(self) -> dict[str, str]:
        return {
            "source": "wikidata",
            "base_url": self.base_url,
            "user_agent_configured": str(bool(os.getenv(self.user_agent_env))),
        }


def main() -> int:
    client = WikidataClient()
    print(client.describe())
    print("TODO: implement Wikidata ingestion in feature/ingestion-rawg-wikidata.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
