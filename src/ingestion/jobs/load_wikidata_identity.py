"""Load bulk Wikidata SPARQL identity data into raw storage."""

from __future__ import annotations

import os

from src.ingestion.cli import build_common_parser
from src.ingestion.pipeline_log import PipelineRunLogger
from src.ingestion.wikidata_client import WikidataClient
from src.ingestion.wikidata_queries import QUERY_NAMES, build_query


def default_limit(client: WikidataClient) -> int:
    return int(os.getenv("WIKIDATA_DEMO_LIMIT", client.source_settings.get("demo_limit", 5000)))


def main(argv: list[str] | None = None) -> int:
    parser = build_common_parser("Load bulk Wikidata SPARQL identity data.")
    parser.add_argument(
        "--query-name",
        choices=("all", *QUERY_NAMES),
        default="all",
        help="Single named query or all default bulk queries.",
    )
    parser.set_defaults(limit=None)
    args = parser.parse_args(argv)

    client = WikidataClient()
    query_limit = args.limit or default_limit(client)
    query_names = list(QUERY_NAMES) if args.query_name == "all" else [args.query_name]
    logger = PipelineRunLogger(
        pipeline_name="wikidata_identity",
        stage_name="raw",
        repository=None if args.dry_run else client.repository,
    )
    logger.mark_started(parameters={"query_names": query_names, "limit": query_limit})

    try:
        for query_name in query_names:
            response = client.run_sparql(
                build_query(query_name, limit=query_limit),
                query_name=query_name,
                dry_run=args.dry_run,
                force_refresh=args.force_refresh,
                from_cache_only=args.from_cache_only,
            )
            if response.dry_run:
                print({"query_name": query_name, "planned": response.request_metadata})
                continue
            if client.repository is None:
                raise RuntimeError("Database repository is unavailable for Wikidata identity load")
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
            metrics={"query_count": len(query_names), "limit": query_limit},
        )
        return 0
    except Exception as exc:
        logger.mark_finished(status="failed", error_message=str(exc))
        raise


if __name__ == "__main__":
    raise SystemExit(main())
