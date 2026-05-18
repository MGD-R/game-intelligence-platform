"""Load targeted RAWG game details into raw.rawg_game_details."""

from __future__ import annotations

import os
from pathlib import Path

from src.ingestion.cli import build_common_parser
from src.ingestion.pipeline_log import PipelineRunLogger
from src.ingestion.rawg_client import RawgClient


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
    return int(os.getenv("RAWG_DETAILS_LIMIT", "0"))


def main(argv: list[str] | None = None) -> int:
    parser = build_common_parser("Load targeted RAWG game details.")
    parser.add_argument("--ids", help="Comma-separated RAWG ids.")
    parser.add_argument("--ids-file", help="File with one RAWG id per line.")
    parser.set_defaults(limit=default_details_limit())
    args = parser.parse_args(argv)

    client = RawgClient()
    logger = PipelineRunLogger(
        pipeline_name="rawg_details",
        stage_name="raw",
        repository=None if args.dry_run else client.repository,
    )
    logger.mark_started(parameters={"limit": args.limit})

    try:
        ids = parse_ids(args.ids, args.ids_file)
        if args.limit > 0:
            ids = ids[: args.limit]

        for rawg_id in ids:
            response = client.get_game_details(
                rawg_id,
                dry_run=args.dry_run,
                from_cache_only=args.from_cache_only,
                force_refresh=args.force_refresh,
            )
            if response.dry_run:
                print({"id": rawg_id, "planned": response.request_metadata})
                continue
            if client.repository is None:
                raise RuntimeError("Database repository is unavailable for RAWG details load")
            client.repository.insert_raw_record(
                table_name="raw.rawg_game_details",
                endpoint=response.endpoint,
                request_hash=response.request_hash,
                source_record_id=str(rawg_id),
                response_json=response.payload if isinstance(response.payload, dict) else {},
                response_hash=response.response_hash,
                response_storage_path=response.cache_path,
                from_cache=response.from_cache,
                http_status=response.http_status,
                error_message=response.error_message,
            )

        logger.mark_finished(status="completed", metrics={"requested_ids": len(ids)})
        return 0
    except Exception as exc:
        logger.mark_finished(status="failed", error_message=str(exc))
        raise


if __name__ == "__main__":
    raise SystemExit(main())
