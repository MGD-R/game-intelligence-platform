"""Steam enrichment placeholder."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class SteamClient:
    base_url: str = "https://store.steampowered.com/api"
    api_key_env: str = "STEAM_API_KEY"

    def describe(self) -> dict[str, str]:
        return {
            "source": "steam",
            "base_url": self.base_url,
            "api_key_configured": str(bool(os.getenv(self.api_key_env))),
        }


def main() -> int:
    client = SteamClient()
    print(client.describe())
    print("TODO: implement targeted Steam enrichment after the MVP ingestion branch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
