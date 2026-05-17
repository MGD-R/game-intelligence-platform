"""Load targeted Wikidata identity rows for RAWG games already present in staging."""

from __future__ import annotations

from src.ingestion.cli import build_common_parser
from src.ingestion.pipeline_log import PipelineRunLogger
from src.ingestion.repository import IngestionRepository
from src.ingestion.wikidata_client import WikidataClient
from src.ingestion.wikidata_queries import rawg_ids_query


def load_rawg_slugs(repository: IngestionRepository, *, limit: int) -> list[str]:
    rows = repository.fetch_staging_rows("stg.source_games", source="rawg", limit=limit)
    slugs: list[str] = []
    for row in rows:
        rawg_slug = row.get("slug")
        if rawg_slug in (None, ""):
            continue
        slugs.append(str(rawg_slug))
    return slugs


def chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def build_parser():  # type: ignore[no-untyped-def]
    parser = build_common_parser("Load targeted Wikidata rows by RAWG IDs from staging.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of RAWG slugs per SPARQL VALUES batch.",
    )
    parser.set_defaults(limit=400)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be greater than zero")

    repository = IngestionRepository()
    rawg_slugs = load_rawg_slugs(repository, limit=max(0, args.limit))
    batches = chunked(rawg_slugs, args.batch_size)
    client = WikidataClient()
    logger = PipelineRunLogger(
        pipeline_name="wikidata_by_rawg_ids",
        stage_name="raw",
        repository=None if args.dry_run else client.repository,
    )
    logger.mark_started(
        parameters={
            "rawg_slug_count": len(rawg_slugs),
            "batch_count": len(batches),
            "batch_size": args.batch_size,
            "limit": args.limit,
        }
    )

    try:
        if not rawg_slugs:
            if args.dry_run:
                print(
                    {
                        "batch_count": 0,
                        "rawg_slugs": [],
                        "planned": {
                            "selection_source": "stg.source_games",
                            "selection_status": "empty",
                        },
                    }
                )
                logger.mark_finished(
                    status="completed",
                    metrics={"rawg_slug_count": 0, "batch_count": 0, "batch_size": args.batch_size},
                )
                return 0
            raise RuntimeError("No RAWG staging slugs found. Run `make rawg-staging` first.")

        batch_width = max(4, len(str(max(1, len(batches)))))
        for index, batch in enumerate(batches, start=1):
            query_name = f"rawg_ids_batch_{index:0{batch_width}d}"
            response = client.run_sparql(
                rawg_ids_query(batch),
                query_name=query_name,
                dry_run=args.dry_run,
                force_refresh=args.force_refresh,
                from_cache_only=args.from_cache_only,
            )
            if response.dry_run:
                print(
                    {
                        "batch": index,
                        "batch_count": len(batches),
                        "rawg_slugs": batch,
                        "planned": response.request_metadata,
                    }
                )
                continue
            if client.repository is None:
                raise RuntimeError("Database repository is unavailable for Wikidata RAWG-ID load")
            client.repository.insert_raw_record(
                table_name="raw.wikidata_sparql_results",
                endpoint=response.endpoint,
                request_hash=response.request_hash,
                source_record_id=query_name,
                response_json=response.payload if isinstance(response.payload, dict) else {},
                response_hash=response.response_hash,
                response_storage_path=response.cache_path,
                from_cache=response.from_cache,
                http_status=response.http_status,
                error_message=response.error_message,
            )

        logger.mark_finished(
            status="completed",
            metrics={
                "rawg_slug_count": len(rawg_slugs),
                "batch_count": len(batches),
                "batch_size": args.batch_size,
            },
        )
        return 0
    except Exception as exc:
        logger.mark_finished(status="failed", error_message=str(exc))
        raise


if __name__ == "__main__":
    raise SystemExit(main())
