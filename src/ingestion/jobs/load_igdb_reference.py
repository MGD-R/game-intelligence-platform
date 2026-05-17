"""Load IGDB reference endpoints into raw.igdb_reference_data."""

from __future__ import annotations

from src.ingestion.cli import build_common_parser
from src.ingestion.igdb_client import IGDBClient
from src.ingestion.igdb_queries import REFERENCE_ENDPOINTS
from src.ingestion.pipeline_log import PipelineRunLogger


def main(argv: list[str] | None = None) -> int:
    parser = build_common_parser("Load IGDB reference endpoints.")
    parser.add_argument("--endpoint", choices=("all", *REFERENCE_ENDPOINTS), default="all")
    args = parser.parse_args(argv)
    client = IGDBClient()
    endpoints = list(REFERENCE_ENDPOINTS) if args.endpoint == "all" else [args.endpoint]
    logger = PipelineRunLogger(
        pipeline_name="igdb_reference",
        stage_name="raw",
        repository=None if args.dry_run else client.repository,
    )
    logger.mark_started(parameters={"dry_run": args.dry_run, "endpoints": endpoints})

    try:
        for endpoint in endpoints:
            response = client.get_reference(
                endpoint,
                dry_run=args.dry_run,
                force_refresh=args.force_refresh,
                from_cache_only=args.from_cache_only,
            )
            if response.dry_run:
                print({"endpoint": endpoint, "planned": response.request_metadata})
                continue
            if client.repository is None:
                raise RuntimeError("Database repository is unavailable for IGDB reference load")
            client.repository.insert_raw_record(
                table_name="raw.igdb_reference_data",
                endpoint=response.endpoint,
                request_hash=response.request_hash,
                source_record_id=endpoint,
                response_json={"items": response.payload}
                if isinstance(response.payload, list)
                else {},
                response_hash=response.response_hash,
                response_storage_path=response.cache_path,
                from_cache=response.from_cache,
                http_status=response.http_status,
                error_message=response.error_message,
            )
        logger.mark_finished(status="completed", metrics={"endpoint_count": len(endpoints)})
        return 0
    except Exception as exc:
        logger.mark_finished(status="failed", error_message=str(exc))
        raise


if __name__ == "__main__":
    raise SystemExit(main())
