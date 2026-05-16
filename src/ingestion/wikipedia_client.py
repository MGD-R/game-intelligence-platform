"""Wikipedia enrichment placeholder."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class WikipediaClient:
    base_url: str = "https://en.wikipedia.org/api/rest_v1"
    user_agent_env: str = "WIKIMEDIA_USER_AGENT"

    def describe(self) -> dict[str, str]:
        return {
            "source": "wikipedia",
            "base_url": self.base_url,
            "user_agent_configured": str(bool(os.getenv(self.user_agent_env))),
        }


def main() -> int:
    client = WikipediaClient()
    print(client.describe())
    print("TODO: implement grounded Wikipedia summaries after canonical entity resolution exists.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
