"""Load targeted IGDB game details into raw.igdb_games."""

from __future__ import annotations

import os
from itertools import islice

from src.ingestion.cli import build_common_parser
from src.ingestion.igdb_auth import load_igdb_settings
from src.ingestion.igdb_client import IGDBClient
from src.ingestion.jobs.select_igdb_ids import select_igdb_ids_from_rows
from src.ingestion.pipeline_log import PipelineRunLogger


def default_details_limit() -> int:
    settings = load_igdb_settings()
    return int(os.getenv("IGDB_DETAILS_LIMIT", settings.get("demo_limit", 50)))


def batched(values: list[int], size: int) -> list[list[int]]:
    batches: list[list[int]] = []
    iterator = iter(values)
    while batch := list(islice(iterator, size)):
        batches.append(batch)
    return batches


def resolve_ids(client: IGDBClient, args) -> list[int]:  # type: ignore[no-untyped-def]
    raw_ids: list[str] = []
    if getattr(args, "ids", None):
        raw_ids.extend(str(item).strip() for item in str(args.ids).split(","))
    if getattr(args, "ids_file", None):
        raw_ids.extend(
            line.strip() for line in open(args.ids_file, "r", encoding="utf-8").read().splitlines()
        )
    if not raw_ids:
        if client.repository is None:
            return []
        rows = client.repository.fetch_staging_rows(
            "stg.source_game_external_ids", source="wikidata"
        )
        raw_ids = select_igdb_ids_from_rows(rows, limit=args.limit)
    resolved = [int(item) for item in raw_ids if item.isdigit()]
    return resolved[: args.limit] if args.limit is not None else resolved


def main(argv: list[str] | None = None) -> int:
    parser = build_common_parser("Load targeted IGDB game details by IDs.")
    parser.add_argument("--ids", help="Comma-separated IGDB IDs.")
    parser.add_argument("--ids-file", help="File with one IGDB ID per line.")
    parser.set_defaults(limit=default_details_limit())
    args = parser.parse_args(argv)

    client = IGDBClient()
    logger = PipelineRunLogger(
        pipeline_name="igdb_games",
        stage_name="raw",
        repository=None if args.dry_run else client.repository,
    )
    logger.mark_started(parameters={"dry_run": args.dry_run, "limit": args.limit})

    ids = resolve_ids(client, args)
    if args.dry_run:
        print(
            {
                "source": "igdb",
                "ids": ids[: min(len(ids), 10)],
                "batch_size": int(client.source_settings.get("max_items_per_request", 500)),
                "limit": args.limit,
            }
        )
        logger.mark_finished(status="completed", metrics={"planned_ids": len(ids)})
        return 0

    if not ids:
        raise RuntimeError(
            "No IGDB IDs available for targeted load. "
            "Run `make wikidata-by-rawg`, `make wikidata-staging`, and `make staging` first."
        )
    if client.repository is None:
        raise RuntimeError("Database repository is unavailable for IGDB game load.")

    batch_size = int(client.source_settings.get("max_items_per_request", 500))
    inserted = 0
    for batch in batched(ids, batch_size):
        response = client.get_games_by_ids(
            batch,
            dry_run=False,
            force_refresh=args.force_refresh,
            from_cache_only=args.from_cache_only,
        )
        payload = response.payload if isinstance(response.payload, list) else []
        for item in payload:
            if not isinstance(item, dict) or item.get("id") is None:
                continue
            client.repository.insert_raw_record(
                table_name="raw.igdb_games",
                endpoint=response.endpoint,
                request_hash=response.request_hash,
                source_record_id=str(item["id"]),
                response_json=item,
                response_hash=response.response_hash,
                response_storage_path=response.cache_path,
                from_cache=response.from_cache,
                http_status=response.http_status,
                error_message=response.error_message,
            )
            inserted += 1
    logger.mark_finished(
        status="completed", metrics={"inserted": inserted, "requested_ids": len(ids)}
    )
    print({"inserted": inserted, "requested_ids": len(ids)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
