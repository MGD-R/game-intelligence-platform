"""Load RAWG reference endpoints into raw.rawg_reference_data."""

from __future__ import annotations

from src.ingestion.cli import build_common_parser
from src.ingestion.pipeline_log import PipelineRunLogger
from src.ingestion.rawg_client import RawgClient

REFERENCE_LOADERS = {
    "genres": RawgClient.get_genres,
    "platforms": RawgClient.get_platforms,
    "stores": RawgClient.get_stores,
    "tags": RawgClient.get_tags,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_common_parser("Load RAWG reference endpoints.")
    args = parser.parse_args(argv)
    client = RawgClient()
    logger = PipelineRunLogger(
        pipeline_name="rawg_reference",
        stage_name="raw",
        repository=None if args.dry_run else client.repository,
    )
    logger.mark_started(parameters={"dry_run": args.dry_run})

    try:
        for reference_type, loader in REFERENCE_LOADERS.items():
            response = loader(
                client,
                dry_run=args.dry_run,
                from_cache_only=args.from_cache_only,
                force_refresh=args.force_refresh,
            )
            if response.dry_run:
                print({"reference_type": reference_type, "planned": response.request_metadata})
                continue
            if client.repository is None:
                raise RuntimeError("Database repository is unavailable for RAWG reference load")
            client.repository.insert_raw_record(
                table_name="raw.rawg_reference_data",
                endpoint=response.endpoint,
                request_hash=response.request_hash,
                source_record_id=reference_type,
                response_json=response.payload if isinstance(response.payload, dict) else {},
                response_hash=response.response_hash,
                response_storage_path=response.cache_path,
                from_cache=response.from_cache,
                http_status=response.http_status,
                error_message=response.error_message,
            )
        logger.mark_finished(status="completed")
        return 0
    except Exception as exc:
        logger.mark_finished(status="failed", error_message=str(exc))
        raise


if __name__ == "__main__":
    raise SystemExit(main())
