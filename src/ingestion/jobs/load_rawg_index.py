"""Load paginated RAWG game index into raw.rawg_game_index."""

from __future__ import annotations

import os

from src.ingestion.cli import build_common_parser
from src.ingestion.pipeline_log import PipelineRunLogger
from src.ingestion.rawg_client import RawgClient


def demo_mode_enabled() -> bool:
    return os.getenv("DEMO_MODE", "true").lower() not in {"0", "false", "no"}


def default_page_limit(client: RawgClient) -> int:
    if demo_mode_enabled():
        return int(
            os.getenv(
                "RAWG_DISCOVERY_PAGE_LIMIT",
                client.source_settings.get("demo_page_limit", 10),
            )
        )
    return int(os.getenv("RAWG_DISCOVERY_PAGE_LIMIT", 10))


def default_page_size(client: RawgClient) -> int:
    return int(os.getenv("RAWG_PAGE_SIZE", client.source_settings.get("default_page_size", 40)))


def main(argv: list[str] | None = None) -> int:
    parser = build_common_parser("Load paginated RAWG game index.")
    parser.add_argument("--page-size", type=int, help="RAWG page size.")
    parser.add_argument("--page-limit", type=int, help="Number of pages to fetch.")
    parser.add_argument("--ordering", default="-added", help="RAWG ordering field.")
    parser.add_argument("--dates", help="RAWG dates filter.")
    parser.add_argument("--platforms", help="RAWG platforms filter.")
    parser.add_argument("--genres", help="RAWG genres filter.")
    args = parser.parse_args(argv)

    client = RawgClient()
    page_size = args.page_size or default_page_size(client)
    page_limit = args.page_limit or default_page_limit(client)
    logger = PipelineRunLogger(
        pipeline_name="rawg_index",
        stage_name="raw",
        repository=None if args.dry_run else client.repository,
    )
    logger.mark_started(
        parameters={
            "page_size": page_size,
            "page_limit": page_limit,
            "ordering": args.ordering,
        }
    )

    try:
        for page in range(1, page_limit + 1):
            response = client.get_games(
                page=page,
                page_size=page_size,
                ordering=args.ordering,
                dates=args.dates,
                platforms=args.platforms,
                genres=args.genres,
                dry_run=args.dry_run,
                from_cache_only=args.from_cache_only,
                force_refresh=args.force_refresh,
            )
            if response.dry_run:
                print({"page": page, "planned": response.request_metadata})
                continue
            if client.repository is None:
                raise RuntimeError("Database repository is unavailable for RAWG index load")
            client.repository.insert_raw_record(
                table_name="raw.rawg_game_index",
                endpoint=response.endpoint,
                request_hash=response.request_hash,
                source_record_id=f"page:{page}",
                response_json=response.payload if isinstance(response.payload, dict) else {},
                response_hash=response.response_hash,
                response_storage_path=response.cache_path,
                from_cache=response.from_cache,
                http_status=response.http_status,
                error_message=response.error_message,
            )
            payload = response.payload if isinstance(response.payload, dict) else {}
            if not payload.get("next"):
                break
        logger.mark_finished(status="completed")
        return 0
    except Exception as exc:
        logger.mark_finished(status="failed", error_message=str(exc))
        raise


if __name__ == "__main__":
    raise SystemExit(main())
