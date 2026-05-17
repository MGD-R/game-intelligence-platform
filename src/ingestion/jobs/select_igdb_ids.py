"""Select IGDB IDs from Wikidata staging external IDs."""

from __future__ import annotations

import os
from pathlib import Path

from src.ingestion.cli import build_common_parser
from src.ingestion.igdb_auth import load_igdb_settings
from src.ingestion.repository import IngestionRepository


def default_limit() -> int:
    settings = load_igdb_settings()
    return int(os.getenv("IGDB_DETAILS_LIMIT", settings.get("demo_limit", 50)))


def select_igdb_ids_from_rows(
    rows: list[dict[str, object]],
    *,
    limit: int | None = None,
) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if row.get("source") != "wikidata" or row.get("external_source") != "igdb":
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
    parser = build_common_parser("Select IGDB IDs from Wikidata staging external IDs.")
    parser.add_argument("--output-file", help="Optional output file with one IGDB ID per line.")
    parser.set_defaults(limit=default_limit())
    args = parser.parse_args(argv)

    if args.dry_run:
        print(
            {
                "selection_source": "stg.source_game_external_ids",
                "filters": {"source": "wikidata", "external_source": "igdb"},
                "limit": args.limit,
                "output_file": args.output_file,
            }
        )
        return 0

    repository = IngestionRepository()
    rows = repository.fetch_staging_rows("stg.source_game_external_ids", source="wikidata")
    igdb_ids = select_igdb_ids_from_rows(rows, limit=args.limit)
    if not igdb_ids:
        raise RuntimeError(
            "No IGDB IDs found in Wikidata staging external IDs. "
            "Run `make wikidata-demo` and `make staging` first."
        )
    if args.output_file:
        Path(args.output_file).write_text("\n".join(igdb_ids) + "\n", encoding="utf-8")
    print({"selected_count": len(igdb_ids), "ids": igdb_ids, "output_file": args.output_file})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
