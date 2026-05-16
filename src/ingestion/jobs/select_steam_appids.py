"""Select Steam AppIDs from existing Wikidata staging external IDs."""

from __future__ import annotations

import os
from pathlib import Path

from src.ingestion.cli import build_common_parser
from src.ingestion.repository import IngestionRepository
from src.ingestion.steam_client import load_steam_settings


def default_limit() -> int:
    settings = load_steam_settings()
    return int(os.getenv("STEAM_DETAILS_LIMIT", settings.get("demo_limit", 50)))


def select_steam_appids_from_rows(
    rows: list[dict[str, object]],
    *,
    limit: int | None = None,
) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if row.get("source") != "wikidata":
            continue
        if row.get("external_source") != "steam":
            continue
        external_id = str(row.get("external_id") or "").strip()
        if not external_id or external_id in seen:
            continue
        seen.add(external_id)
        selected.append(external_id)
        if limit is not None and len(selected) >= limit:
            break
    return selected


def main(argv: list[str] | None = None) -> int:
    parser = build_common_parser("Select Steam AppIDs from Wikidata staging external IDs.")
    parser.add_argument("--output-file", help="Optional output file with one Steam AppID per line.")
    parser.set_defaults(limit=default_limit())
    args = parser.parse_args(argv)

    if args.dry_run:
        print(
            {
                "selection_source": "stg.source_game_external_ids",
                "filters": {
                    "source": "wikidata",
                    "external_source": "steam",
                },
                "limit": args.limit,
                "output_file": args.output_file,
            }
        )
        return 0

    repository = IngestionRepository()
    rows = repository.fetch_staging_rows("stg.source_game_external_ids", source="wikidata")
    appids = select_steam_appids_from_rows(rows, limit=args.limit)
    if not appids:
        raise RuntimeError(
            "No Steam AppIDs found in Wikidata staging external IDs. "
            "Run `make wikidata-demo` and `make staging` first."
        )
    if args.output_file:
        Path(args.output_file).write_text("\n".join(appids) + "\n", encoding="utf-8")
    print(
        {
            "selected_count": len(appids),
            "ids": appids,
            "output_file": args.output_file,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
