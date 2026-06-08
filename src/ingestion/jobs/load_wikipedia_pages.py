"""Load targeted Wikipedia summaries into raw.wikipedia_pages."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from src.ingestion.base_client import HTTPStatusError
from src.ingestion.cli import build_common_parser
from src.ingestion.jobs.select_wikipedia_pages import (
    default_limit,
    select_pages_from_url_rows,
    title_from_url,
)
from src.ingestion.pipeline_log import PipelineRunLogger
from src.ingestion.wikipedia_client import WikipediaClient


def default_page_limit() -> int:
    return int(os.getenv("WIKIPEDIA_PAGE_LIMIT", default_limit()))


def default_retry_limit() -> int:
    return int(os.getenv("WIKIPEDIA_429_RETRY_LIMIT", "5"))


def default_retry_backoff_seconds() -> int:
    return int(os.getenv("WIKIPEDIA_429_BACKOFF_SECONDS", "60"))


def parse_pages_file(path: str) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        values.append(json.loads(stripped))
    return values


def normalize_selection(
    *,
    title: str | None = None,
    language: str | None = None,
    pages_file: str | None = None,
) -> list[dict[str, str]]:
    if title:
        return [
            {
                "source_game_id": "",
                "qid": "",
                "language": language or "en",
                "title": title,
                "url": "",
                "url_type": f"{language or 'en'}wiki",
            }
        ]
    if pages_file:
        return parse_pages_file(pages_file)
    return []


def select_missing_pages_from_rows(
    url_rows: list[dict[str, object]],
    description_rows: list[dict[str, object]],
    *,
    limit: int | None = None,
) -> list[dict[str, str]]:
    covered_game_ids = {
        str(row.get("source_game_id") or "")
        for row in description_rows
        if row.get("source") == "wikipedia"
        and row.get("description_type") == "summary"
        and str(row.get("description_text") or "").strip()
    }
    language_priority = {"ruwiki": 0, "enwiki": 1}
    selected: list[dict[str, str]] = []
    seen_game_ids: set[str] = set()
    sorted_rows = sorted(
        (
            row
            for row in url_rows
            if row.get("source") == "wikidata"
            and str(row.get("url_type") or "") in language_priority
        ),
        key=lambda row: (
            language_priority[str(row.get("url_type") or "")],
            str(row.get("source_game_id") or ""),
            str(row.get("url") or ""),
        ),
    )
    for row in sorted_rows:
        source_game_id = str(row.get("source_game_id") or "").strip()
        if (
            not source_game_id
            or source_game_id in covered_game_ids
            or source_game_id in seen_game_ids
        ):
            continue
        url_type = str(row.get("url_type") or "")
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        language = "ru" if url_type == "ruwiki" else "en"
        selected.append(
            {
                "source_game_id": source_game_id,
                "qid": source_game_id,
                "language": language,
                "title": title_from_url(url),
                "url": url,
                "url_type": url_type,
            }
        )
        seen_game_ids.add(source_game_id)
        if limit is not None and len(selected) >= limit:
            break
    return selected


def build_wrapped_response(
    page: dict[str, str],
    payload: dict[str, Any] | str,
) -> dict[str, Any]:
    return {
        "selection": {
            "qid": page.get("qid"),
            "language": page.get("language"),
            "title": page.get("title"),
            "url": page.get("url"),
            "url_type": page.get("url_type"),
        },
        "response": payload,
    }


def load_page_with_backoff(
    client: WikipediaClient,
    page: dict[str, str],
    *,
    force_refresh: bool,
    from_cache_only: bool,
    retry_limit: int,
    retry_backoff_seconds: int,
):
    attempts = 0
    while True:
        try:
            return client.get_page_summary(
                page["language"],
                page["title"],
                dry_run=False,
                force_refresh=force_refresh,
                from_cache_only=from_cache_only,
            )
        except HTTPStatusError as exc:
            if exc.status_code != 429 or attempts >= retry_limit:
                raise
            attempts += 1
            time.sleep(retry_backoff_seconds)


def load_selected_pages(
    client: WikipediaClient,
    pages: list[dict[str, str]],
    *,
    force_refresh: bool,
    from_cache_only: bool,
    retry_limit: int,
    retry_backoff_seconds: int,
) -> dict[str, int]:
    if client.repository is None:
        raise RuntimeError("Database repository is unavailable for Wikipedia page load")

    loaded_pages = 0
    skipped_pages = 0
    for page in pages:
        try:
            response = load_page_with_backoff(
                client,
                page,
                force_refresh=force_refresh,
                from_cache_only=from_cache_only,
                retry_limit=retry_limit,
                retry_backoff_seconds=retry_backoff_seconds,
            )
        except HTTPStatusError as exc:
            if exc.status_code == 404:
                skipped_pages += 1
                print(
                    {
                        "skipped_page": page["title"],
                        "language": page["language"],
                        "status_code": exc.status_code,
                    }
                )
                continue
            raise

        client.repository.insert_raw_record(
            table_name="raw.wikipedia_pages",
            endpoint=response.endpoint,
            request_hash=response.request_hash,
            source_record_id=f"{page['language']}:{page['title']}",
            response_json=build_wrapped_response(page, response.payload),
            response_hash=response.response_hash,
            response_storage_path=response.cache_path,
            from_cache=response.from_cache,
            http_status=response.http_status,
            error_message=response.error_message,
        )
        loaded_pages += 1

    return {
        "loaded_pages": loaded_pages,
        "skipped_pages": skipped_pages,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_common_parser("Load targeted Wikipedia summary pages.")
    parser.add_argument("--pages-file", help="JSONL file created by select_wikipedia_pages.")
    parser.add_argument("--title", help="Single explicit Wikipedia page title.")
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Select only games that do not yet have a non-empty Wikipedia summary in staging.",
    )
    parser.add_argument(
        "--language",
        choices=("ru", "en"),
        help="Language for explicit --title mode.",
    )
    parser.add_argument(
        "--retry-limit",
        type=int,
        default=default_retry_limit(),
        help="How many page-level retries to allow after HTTP 429.",
    )
    parser.add_argument(
        "--retry-backoff-seconds",
        type=int,
        default=default_retry_backoff_seconds(),
        help="How long to wait before retrying the same page after HTTP 429.",
    )
    parser.set_defaults(limit=default_page_limit())
    args = parser.parse_args(argv)

    explicit_pages = normalize_selection(
        title=args.title,
        language=args.language,
        pages_file=args.pages_file,
    )
    preview = (
        explicit_pages[0]
        if explicit_pages
        else {
            "language": "en",
            "title": "Selected from Wikidata sitelinks",
        }
    )

    if args.dry_run:
        client = WikipediaClient(repository=None)
        response = client.get_page_summary(
            preview["language"],
            preview["title"],
            dry_run=True,
            force_refresh=args.force_refresh,
            from_cache_only=args.from_cache_only,
        )
        print(
            {
                "selection_source": (
                    "explicit_pages"
                    if explicit_pages
                    else (
                        "wikidata_missing_summaries"
                        if args.missing_only
                        else "wikidata_sitelinks"
                    )
                ),
                "limit": args.limit,
                "request_preview": response.request_metadata,
            }
        )
        return 0

    client = WikipediaClient()
    logger = PipelineRunLogger(
        pipeline_name="wikipedia_pages",
        stage_name="raw",
        repository=client.repository,
    )
    logger.mark_started(parameters={"limit": args.limit, "missing_only": args.missing_only})

    try:
        pages = explicit_pages
        if not pages:
            if client.repository is None:
                raise RuntimeError("Database repository is unavailable for Wikipedia selection")
            url_rows = client.repository.fetch_staging_rows(
                "stg.source_game_urls",
                source="wikidata",
            )
            if args.missing_only:
                description_rows = client.repository.fetch_staging_rows(
                    "stg.source_game_descriptions",
                    source="wikipedia",
                )
                pages = select_missing_pages_from_rows(
                    url_rows,
                    description_rows,
                    limit=max(1, args.limit),
                )
            else:
                pages = select_pages_from_url_rows(url_rows, limit=max(1, args.limit))
        if not pages:
            raise RuntimeError(
                "No Wikipedia sitelinks found for targeted summaries. "
                "Run `make wikidata-by-rawg`, `make wikidata-staging`, and `make staging` first."
            )
        pages = pages[: max(1, args.limit)]

        metrics = load_selected_pages(
            client,
            pages,
            force_refresh=args.force_refresh,
            from_cache_only=args.from_cache_only,
            retry_limit=max(0, args.retry_limit),
            retry_backoff_seconds=max(1, args.retry_backoff_seconds),
        )
        logger.mark_finished(
            status="completed",
            metrics={"requested_pages": len(pages), **metrics},
        )
        print({"loaded_pages": pages})
        return 0
    except Exception as exc:
        logger.mark_finished(status="failed", error_message=str(exc))
        raise


if __name__ == "__main__":
    raise SystemExit(main())
