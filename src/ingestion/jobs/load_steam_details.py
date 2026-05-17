"""Load targeted Steam Store appdetails into raw.steam_app_details."""

from __future__ import annotations

import os
from pathlib import Path

from src.ingestion.cli import build_common_parser
from src.ingestion.jobs.select_steam_appids import (
    default_limit,
    select_steam_appids_from_rows,
)
from src.ingestion.pipeline_log import PipelineRunLogger
from src.ingestion.steam_client import SteamClient


def parse_ids(raw_ids: str | None, ids_file: str | None) -> list[str]:
    values: list[str] = []
    if raw_ids:
        values.extend(part.strip() for part in raw_ids.split(",") if part.strip())
    if ids_file:
        values.extend(
            line.strip()
            for line in Path(ids_file).read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    return values


def default_details_limit() -> int:
    return int(os.getenv("STEAM_DETAILS_LIMIT", default_limit()))


def resolve_selected_ids(
    client: SteamClient,
    *,
    explicit_ids: list[str],
    limit: int,
) -> list[str]:
    if explicit_ids:
        return explicit_ids[:limit]
    if client.repository is None:
        return []
    rows = client.repository.fetch_staging_rows("stg.source_game_external_ids", source="wikidata")
    return select_steam_appids_from_rows(rows, limit=limit)


def main(argv: list[str] | None = None) -> int:
    parser = build_common_parser("Load targeted Steam Store appdetails.")
    parser.add_argument("--ids", help="Comma-separated Steam AppIDs.")
    parser.add_argument("--ids-file", help="File with one Steam AppID per line.")
    parser.set_defaults(limit=default_details_limit())
    args = parser.parse_args(argv)

    client = SteamClient(repository=None)
    explicit_ids = parse_ids(args.ids, args.ids_file)
    preview_id = explicit_ids[0] if explicit_ids else "selected-from-staging"

    if args.dry_run:
        response = client.get_app_details(
            preview_id,
            dry_run=True,
            force_refresh=args.force_refresh,
            from_cache_only=args.from_cache_only,
        )
        print(
            {
                "selection_source": "explicit_ids" if explicit_ids else "staging_external_ids",
                "limit": args.limit,
                "request_preview": response.request_metadata,
            }
        )
        return 0

    client = SteamClient()
    logger = PipelineRunLogger(
        pipeline_name="steam_details",
        stage_name="raw",
        repository=client.repository,
    )
    logger.mark_started(parameters={"limit": args.limit})

    try:
        appids = resolve_selected_ids(client, explicit_ids=explicit_ids, limit=max(1, args.limit))
        if not appids:
            raise RuntimeError(
                "No Steam AppIDs found for targeted enrichment. "
                "Run `make wikidata-by-rawg`, `make wikidata-staging`, and `make staging` first."
            )

        for appid in appids:
            response = client.get_app_details(
                appid,
                dry_run=False,
                from_cache_only=args.from_cache_only,
                force_refresh=args.force_refresh,
            )
            if client.repository is None:
                raise RuntimeError("Database repository is unavailable for Steam details load")
            client.repository.insert_raw_record(
                table_name="raw.steam_app_details",
                endpoint=response.endpoint,
                request_hash=response.request_hash,
                source_record_id=str(appid),
                response_json=response.payload if isinstance(response.payload, dict) else {},
                response_hash=response.response_hash,
                response_storage_path=response.cache_path,
                from_cache=response.from_cache,
                http_status=response.http_status,
                error_message=response.error_message,
            )

        logger.mark_finished(status="completed", metrics={"requested_ids": len(appids)})
        print({"loaded_ids": appids})
        return 0
    except Exception as exc:
        logger.mark_finished(status="failed", error_message=str(exc))
        raise


if __name__ == "__main__":
    raise SystemExit(main())
