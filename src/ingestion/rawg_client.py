"""RAWG client placeholder."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class RawgClient:
    base_url: str = "https://api.rawg.io/api"
    api_key_env: str = "RAWG_API_KEY"

    def describe(self) -> dict[str, str]:
        return {
            "source": "rawg",
            "base_url": self.base_url,
            "api_key_configured": str(bool(os.getenv(self.api_key_env))),
        }


def main() -> int:
    client = RawgClient()
    print(client.describe())
    print("TODO: implement RAWG ingestion in feature/ingestion-rawg-wikidata.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
